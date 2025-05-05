# Buy-Sell E-Commerce Backend

A full-featured e-commerce backend built with Django, Django REST Framework, Channels, and Celery. It provides JWT-based authentication, product management, order processing, reviews, chat & notifications, personalized dashboards, search engine, and a recommendation engine.

## 🛠️ Tech Stack

- **Python & Django 5.1**
- **Django REST Framework 3.15** for RESTful APIs
- **Django Channels 4.2 & Daphne** for WebSocket support
- **Celery 5.4 / Redis** for asynchronous tasks
- **PostgreSQL** (via `psycopg2`) for Database
- **Redis** for caching & Channels layer
- **Cloudinary** for media storage
- **drf-spectacular** for OpenAPI/Swagger documentation
- **Pillow** for image handling

## 🚀 Getting Started

1. Clone the repository

   ```bash
   git clone https://github.com/Grapsinho/Buy-Sell-ecommerce.git
   cd Buy-Sell-ecommerce
   ```

2. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables (create a `.env` file):

   ```env
   SECRET_KEY=your_secret_key

   DATABASE_URL=postgres://user:pass@localhost:5432/dbname

   REDIS_URL=redis://localhost:6379/0

   BROKER_URL=amqp://guest:guest@localhost:5672//

   CLOUDINARY_URL=cloudinary://key:secret@cloud_name

   EMAIL_HOST=your_smtp_host
   EMAIL_HOST_USER=your_email
   EMAIL_HOST_PASSWORD=your_email_password
   ```

4. Run migrations

   ```bash
   python manage.py migrate
   ```

5. Create superuser (optional)

   ```bash
   python manage.py createsuperuser
   ```

6. Start services

   ```bash
   # Redis
   redis-server

   # Start Celery worker
   celery -A project_name worker -l info

   # Run Django server (with Daphne for Channels)
   daphne -b 0.0.0.0 -p 8000 project_name.asgi:application
   ```

## 📂 Project Structure

```
├── users/                 # Authentication: JWT, email confirm, password reset
├── product_management/    # Products, categories, media handling
├── orders/                # Order listing, checkout, status & emails
├── review_rating/         # Product reviews & ratings
├── chat_app/              # Real-time chat
├── notification_app       # Real-time notifications
├── dashboard/             # User dashboard: profile, own products, recommendations
├── product_cart/          # Product cart
├── utils/                 # Shared utilities (image optimization, slugify, JWT cookies)
├── wishlist_app/          # Users wishlist
└── requirements.txt       # Project dependencies
```

## 🧑‍💻 Apps Overview

1. **Users**

   - Custom JWT Authentication via HTTP-only cookies (DRF + Channels)
   - Email Confirmation (6-digit code cached 60s + 10m confirmed flag)
   - Registration, Login/Logout, Refresh Tokens, Password Reset
   - Avatar Upload with PIL optimization

2. **Product Management**

   - CRUD with multipart uploads (text + up to 6 images + metadata)
   - Filtering (price, stock, condition, category), Ordering, Pagination
   - Search by product or seller
   - Category Hierarchy endpoints for parent/child selection

3. **Orders**

   - List & Detail with status milestones (Preparing → In Transit → Delivered)
   - Default Address fetch & Checkout with Idempotency-Key
   - Async Emails on order placed/delivered via Celery tasks

4. **Review & Rating**

   - One Review per User enforced in serializer
   - CRUD (public GET, auth POST, owner PATCH/PUT, owner/admin DELETE)
   - Average Rating auto-calculated, Limit/Offset pagination

5. **Chat & Notifications**

   - REST: list/create chats & messages, mark-read on fetch
   - WebSockets: real-time message send/delete & notification streams via Channels

6. **Dashboard**
   - Profile retrieve/update
   - My Products: cached ID list, prefetch feature media, ordering & filters
   - Recommendations: weighted by cart (×3) & wishlist (×2), cache + signal invalidation, fallback bestsellers

## 🤖 Recommendation Logic

My recommendation engine weights categories from an user’s recent activity:

- **Lookback window:** 180 days (configurable via LOOKBACK_DAYS)
- **Signal weights:** items in cart count triple (CART_WEIGHT=3), wishlist double (WISHLIST_WEIGHT=2)
- **Exclusions:** removes products the user owns, purchased recently, or already in their cart/wishlist
- **Grouping:** aggregates weights at the parent category level, then distributes to eligible child categories
- **Scoring:** annotates active, in-stock products with a score based on category weights, then orders by -score, -units_sold, and -average_rating
- **Fallback:** if no cart/wishlist signals, returns top-selling products by units_sold

## 🔍 Search Logic

I use PostgreSQL full-text search to deliver relevant product results:

- **Input sanitization:** strips non-alphanumeric characters to prevent tsquery injection

- **Tokenization:** splits query into words; applies prefix matching (:<asterisk>) on the last token

- **Weighted search vector:** boosts name matches over description (weights A and B)

- **Search query construction:** joins tokens with <-> for proximity, uses raw search type for advanced syntax

- **Ranking:** annotates each product with a rank via SearchRank, filters out ranks below 0.3, then orders by descending rank

- **Mode options:** supports an “owner” mode for seller username lookups via simple icontains

## ⚙️ Caching Strategy

- **Cache Layer:** Redis (configured via `django-redis`)
- **TTL:** 5 - 30 minutes, Versioning via cache keys
- **Cached Entities:** own-product IDs, recommendation IDs, order IDs
- **Invalidation:** Django signals on create/update/delete in `CartItem`, `WishlistItem`, `OrderItem`, `Product`

## 🔄 Asynchronous Tasks

Celery for email notifications and background jobs:

- `send_order_placed_email`
- `send_order_delivered_email`

**Broker:** Redis

## 📜 API Documentation

Automatically generated OpenAPI schema via `drf-spectacular`:

- **Swagger UI:** `/api/docs/` (or `/api/schema/swagger-ui/`)
- **Raw JSON schema:** `/api/schema/`

## 🔒 Security & Best Practices

- JWT stored in secure, HTTP-only cookies (`SameSite=None`)
- Throttling on email confirmation & login attempts
- Input Validation in serializers and upload handlers
- Permissions enforced via DRF `IsAuthenticated` and custom checks
