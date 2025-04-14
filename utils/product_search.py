from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

def apply_active_filter(queryset, request):
    """
    Filter the queryset to only include active products for GET requests.
    """
    if request.method == 'GET':
        return queryset.filter(is_active=True)
    return queryset


def apply_full_text_search(queryset, request):
    """
    If a non-empty 'q' parameter is provided in the request, apply PostgreSQL full-text search 
    on the product name, description, and optionally the seller's full_username if the 'owner'
    parameter is present. Annotates each result with a relevance rank and filters out low-rank entries.
    """
    search_text = request.query_params.get('q', '').strip()
    if search_text:
        owner_search = request.query_params.get('owner', '').strip()
        # Build the search vector with weights for each field.
        search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
        if owner_search:
            search_vector += SearchVector('seller__full_username', weight='C')
        
        search_query = SearchQuery(search_text)
        queryset = queryset.annotate(
            rank=SearchRank(search_vector, search_query)
        ).filter(rank__gt=0.0).order_by('-rank')
    return queryset
