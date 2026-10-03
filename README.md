# ViserTrip — Multi-Tenant SaaS Travel & Visa Management Platform

> A complete SaaS platform where multiple travel agencies can subscribe and operate independently — each with their own database, admin panel, website, and branding.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Apps & Modules](#apps--modules)
- [Multi-Tenant System](#multi-tenant-system)
- [User Roles](#user-roles)
- [Development Phases](#development-phases)

---

## Overview

**ViserTrip** is a multi-tenant SaaS platform built with Django. Each travel agency (tenant) gets:

- A dedicated PostgreSQL database
- An isolated admin panel
- A public-facing website with CMS
- Subdomain or custom domain support
- Independent bookings, visa, payments & analytics

The platform operates at **three levels**: Super Admin → Agency Admin → Customer.

---

## Architecture

```
Super Admin (Platform Owner)
│
├── Tenant: ABC Travel     → abc_travel_db     → abc-travel.softobro.com
├── Tenant: XYZ Travels    → xyz_travels_db    → xyz-travels.softobro.com
└── Tenant: Viser Agency   → viser_agency_db   → viser-agency.softobro.com
```

**Automatic provisioning** on new agency registration:
1. Create tenant account & generate unique Tenant ID
2. Provision a new PostgreSQL database
3. Run tenant migrations
4. Create default admin, roles, subdomain, and CMS config
5. Send welcome email with credentials

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.x, Django 5.0, Django REST Framework |
| **Database** | PostgreSQL (separate DB per tenant) |
| **Frontend** | HTML5, CSS3, Bootstrap 5, HTMX, Alpine.js, Chart.js |
| **Task Queue** | Celery + Redis |
| **Auth** | Django Auth, django-allauth, 2FA |
| **Storage** | Cloudinary / Amazon S3 |
| **Static Files** | WhiteNoise |
| **Deployment** | Docker, Nginx, Gunicorn |

---

## Project Structure

```
travel/
├── config/                  # Django settings, URLs, WSGI/ASGI, DB router
├── apps/
│   ├── core/                # Base models, middleware, utilities
│   ├── accounts/            # Custom User model, auth views
│   ├── superadmin/          # Super Admin dashboard & management
│   ├── tenants/             # Tenant model, provisioning, admin panel
│   ├── subscriptions/       # SaaS plans, lifecycle, Celery tasks
│   ├── domains/             # Domain/subdomain routing & verification
│   ├── travel_packages/     # Tour packages management
│   ├── destinations/        # Countries, cities, destinations
│   ├── visa/                # Visa services & applications
│   ├── bookings/            # Booking management & workflow
│   ├── payments/            # Payment recording & transactions
│   ├── coupons/             # Coupon & discount management
│   ├── cms/                 # Tenant website CMS
│   ├── notifications/       # In-app & email notifications
│   ├── support/             # Support ticket system
│   ├── reviews/             # Customer reviews
│   ├── kyc/                 # KYC document verification
│   ├── analytics/           # Platform & tenant analytics
│   └── bus/                 # Bus ticket scheduling
├── templates/               # Django HTML templates
├── static/                  # CSS, JS, images
├── media/                   # User-uploaded files
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
└── manage.py
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis 6+
- Node.js (optional, for asset compilation)

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd travel

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env
# Edit .env with your credentials

# 5. Apply main database migrations
python manage.py migrate

# 6. Create a Super Admin
python manage.py createsuperuser

# 7. Start Redis (in a separate terminal)
redis-server

# 8. Start Celery worker (in a separate terminal)
celery -A config worker -l info

# 9. Run the development server
python manage.py runserver
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Main PostgreSQL credentials |
| `DB_HOST` / `DB_PORT` | Database host and port |
| `REDIS_URL` | Redis connection URL |
| `CELERY_BROKER_URL` | Celery broker (Redis) |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP email credentials |
| `CLOUDINARY_*` | Cloudinary storage credentials |
| `BASE_DOMAIN` | Platform root domain (e.g. `softobro.com`) |
| `SUPERADMIN_URL_PREFIX` | URL prefix for super admin panel |

---

## Apps & Modules

| App | Purpose |
|---|---|
| `accounts` | User registration, login, password reset, 2FA, KYC |
| `superadmin` | Platform-level dashboard, tenant & subscription management |
| `tenants` | Tenant admin panel, agency settings, staff management |
| `subscriptions` | SaaS plans (Starter/Pro/Enterprise), billing lifecycle |
| `domains` | Subdomain auto-generation, custom domain verification |
| `travel_packages` | Tour package CRUD, image gallery, seat management |
| `destinations` | Countries, cities, destination pages |
| `visa` | Visa service catalog, applications, document uploads |
| `bookings` | Full booking workflow, status tracking, invoices |
| `payments` | Payment recording, transaction history |
| `coupons` | Discount codes with fixed/percentage amounts |
| `cms` | Tenant website builder (hero, about, FAQ, blog, SEO) |
| `analytics` | Chart.js dashboards for revenue, bookings, visa stats |
| `notifications` | In-app + email alerts for bookings, payments, subscriptions |
| `support` | Customer ↔ admin ticket system with file attachments |
| `kyc` | Document upload, admin review, approval/rejection |
| `reviews` | Customer rating & review system |
| `bus` | Bus ticket scheduling integrated with packages |

---

## Multi-Tenant System

- **Database Isolation**: Every tenant has a separate PostgreSQL database. No data is shared between tenants.
- **DB Router**: `config/` contains a custom database router that dynamically routes queries to the correct tenant database based on the active request context.
- **Middleware**: `TenantMiddleware` identifies the tenant from the request hostname and sets the database context for the duration of the request.
- **Domain Routing**: Requests are resolved via subdomain (e.g., `abc-travel.softobro.com`) or custom domain and mapped to the corresponding tenant.

---

## User Roles

| Role | Access |
|---|---|
| **Super Admin** | Full platform control — manage tenants, subscriptions, analytics, global settings |
| **Agency Admin** | Full control over own tenant — packages, bookings, visa, CMS, staff |
| **Agency Staff** | Limited tenant access based on assigned permissions |
| **Customer** | Public website — browse packages, book trips, apply for visas, manage profile |

---

## Development Phases

- [x] **Phase 1** — Project foundation, custom User model, base templates
- [x] **Phase 2** — Multi-tenant core (DB router, middleware, domain routing)
- [x] **Phase 3** — Super Admin panel
- [x] **Phase 4** — Subscription system & Celery tasks
- [x] **Phase 5** — Tenant Admin panel (users, destinations, packages, visa)
- [x] **Phase 6** — Booking & visa application system
- [x] **Phase 7** — Payment system & coupons
- [x] **Phase 8** — CMS & tenant website engine
- [ ] **Phase 9** — Customer panel
- [ ] **Phase 10** — Full analytics, notifications, support ticket polish

---

## License

Proprietary — © Softobro. All rights reserved.
