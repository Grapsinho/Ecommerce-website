from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
import re

def apply_active_filter(queryset, request):
    """
    Filter the queryset to only include active products for GET requests.
    """
    if request and request.method == 'GET':
        return queryset.filter(is_active=True)
    return queryset


def sanitize_search_input(input_text: str) -> str:
    """
    Sanitize search input by allowing only alphanumeric characters and whitespace.
    This function removes any special characters that are not letters, numbers, or spaces,
    making the input safer for constructing raw tsquery strings.
    
    Args:
        input_text (str): The raw search query from the user.
    
    Returns:
        str: Sanitized search query.
    """
    return re.sub(r'[^A-Za-z0-9\s]', '', input_text)


def apply_full_text_search(queryset, request):
    """
    Applies full-text search to the queryset on the product's name and description.
    
    Input from the request is first sanitized to remove any special characters. Then,
    the search query is tokenized. The last token is used with a prefix operator to facilitate
    prefix matching.
    
    In "owner" mode, a simple case-insensitive lookup on the seller's full_username is applied.
    
    Args:
        queryset: The initial queryset to filter.
        request: The HTTP request, from which query parameters are extracted.
    
    Returns:
        QuerySet: The modified queryset after applying full-text search.
    """
    # Retrieve and sanitize the search string.
    search_text = request.query_params.get('q', '').strip()
    search_text = sanitize_search_input(search_text)
    mode = request.query_params.get('mode', 'product').strip().lower()

    if not search_text:
        return queryset

    if mode == 'owner':
        return queryset.filter(seller__full_username__icontains=search_text)

    # Tokenize and construct the search query.
    tokens = search_text.split()
    if tokens:
        # Use the last token for prefix matching.
        last_token = tokens.pop()
        if tokens:
            ts_query_str = " <-> ".join(tokens + [f"{last_token}:*"])
        else:
            ts_query_str = f"{last_token}:*"
        search_query = SearchQuery(ts_query_str, search_type='raw')
    else:
        # Fall back to phrase search if token splitting fails.
        search_query = SearchQuery(search_text, search_type='phrase')

    # Build a weighted search vector.
    search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')

    return queryset.annotate(
        rank=SearchRank(search_vector, search_query)
    ).filter(rank__gte=0.3).order_by('-rank')

