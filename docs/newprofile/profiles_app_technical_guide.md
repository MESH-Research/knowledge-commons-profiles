# Profiles App Technical Guide

> **Note**: This documentation refers to knowledge-commons-profiles version 3.15.0

## Overview

The Profiles App is the core user profile management system within the knowledge-commons-profiles Django application. It provides comprehensive functionality for creating, displaying, and managing user profiles with rich academic and social features. The app integrates with WordPress data, external services like Mastodon, and provides extensive customization options for profile presentation.

## Core Architecture

### Data Models (`models.py`)

The Profiles App uses a hybrid approach, combining Django models with WordPress database integration:

#### Primary Models

**Profile Model**
- Central user profile model with comprehensive academic and social fields
- Key fields: `name`, `username`, `email`, `orcid`, `affiliation`, `title`
- Multi-email support: `emails` (ArrayField) for secondary email addresses
- Social media integration: `twitter`, `github`, `mastodon`, `bluesky`
- Academic fields: `academic_interests`, `about_user`, `education`, `publications`
- Visibility controls: Boolean fields for showing/hiding profile sections
- Layout customization: `left_order`, `right_order`, `works_order`
- Citation style preference: `reference_style` with configurable choices
- Role management: `role_overrides` (ArrayField) for custom role display preferences

**AcademicInterest Model**
- Simple text-based model for academic interest tags
- Many-to-many relationship with Profile model
- Used for categorizing and filtering user interests

**CoverImage Model**
- Stores user profile cover/banner images
- Fields: `profile` (ForeignKey), `image` (ImageField)
- Supports image compression and optimization

**ProfileImage Model**
- Stores user avatar/profile images
- Fields: `profile` (ForeignKey), `image` (ImageField)
- Supports image compression and optimization

#### COManage Integration Models

The app integrates with COManage for organizational role management:

**CO Model (Collaborative Organization)**
- Represents a collaborative organization in COManage
- Fields: `co_id`, `name`, `slug`
- Used for organization-level membership tracking

**COU Model (Collaborative Organization Unit)**
- Represents organizational units within a CO
- Fields: `cou_id`, `name`, `co` (ForeignKey to CO)
- Used for departmental/unit-level organization

**Person Model**
- COManage person record integration
- Fields: `co_person_id`, `profile` (ForeignKey)
- Links COManage identities to local profiles

**Role Model**
- User roles within organizations
- Fields: `role_id`, `person` (ForeignKey), `cou` (ForeignKey), `affiliation`, `title`, `organization`, `status`
- Tracks membership status and organizational affiliations

#### WordPress Integration Models

The app maintains read-only access to WordPress data through several models:

**WpUser Model**
- Mirrors WordPress user table structure
- Fields: `user_login`, `user_email`, `display_name`, `user_registered`
- Provides `get_user_data()` method for bulk user operations

**WpBpGroup Model**
- WordPress BuddyPress group integration
- Status choices: public, private, hidden
- Related to group membership and activity tracking

**WpBpActivity Model**
- WordPress activity stream integration
- Tracks user actions, content, and social interactions
- Used for displaying recent user activity

### Views and URL Routing

#### View Module Structure

The views are organized into modular components:

```
newprofile/views/
├── __init__.py
├── health.py         # Health check endpoints
├── home.py           # Home page views
├── members.py        # Member listing and filtering
├── search.py         # Search functionality
├── stats.py          # Statistics endpoints
└── profile/          # Profile-related views
    ├── avatars.py    # Image upload handling
    ├── display.py    # Profile display views
    └── edit.py       # Profile editing views
```

#### Main Views

**Profile Display Views**
- `profile(request, user="")`: Main profile page renderer
- `my_profile(request)`: Authenticated user's own profile
- `profile_info(request, username)`: HTMX profile data endpoint

**Profile Management Views**
- `edit_profile(request)`: Profile editing interface
- `save_profile_order(request, side)`: AJAX profile layout saving
- `save_works_order(request)`: AJAX works ordering
- `save_works_visibility(request)`: AJAX visibility controls

**Image Upload Views** (`views/profile/avatars.py`)
- `upload_avatar(request)`: Profile image upload with compression
- `upload_cover(request)`: Cover image upload with compression

**Member Views** (`views/members.py`)
- `members(request)`: Paginated member directory
- Filter and search capabilities for member listing

**Health Check Views** (`views/health.py`)
- `healthcheck(request)`: Application health status endpoint
- Database connectivity verification

**Statistics Views** (`views/stats.py`)
- `stats(request)`: Usage statistics endpoint
- Protected by basic authentication

**Content Integration Views**
- `works_deposits(request, username, style=None)`: KC Works display
- `mastodon_feed(request, username)`: Social media integration
- `blog_posts(request, username)`: WordPress blog integration
- `mysql_data(request, username)`: WordPress data retrieval

#### URL Configuration (`urls.py`)

The app uses a comprehensive URL structure supporting both traditional views and HTMX endpoints:

**Main Routes**
- `/my-profile/` - Authenticated user profile access
- `/edit-profile/` - Profile editing interface
- `/members/<username>/` - Public profile display

**HTMX Endpoints** (prefixed with `htmx/`)
- Profile data: `/htmx/profile-info/<username>/`
- Social feeds: `/htmx/mastodon-feed/<username>/`
- KC Works: `/htmx/works-deposits/<username>/`
- WordPress data: `/htmx/mysql-data/<username>/`
- Media assets: `/htmx/cover-image/<username>/`, `/htmx/profile-image/<username>/`

**AJAX Endpoints**
- Layout management: `/save-profile-order/<side>/`
- Works management: `/save-works-order/`, `/save-works-visibility/`
- Content editing: `/works-deposits-edit/`

### API Layer (`api.py`)

The API class provides a comprehensive interface for profile data access:

#### Core API Class

**Initialization**
```python
API(request, user, use_wordpress=True, create=False, works_citation_style="MHRA")
```

**Key Methods**
- `get_profile_info()`: Complete profile information dictionary
- `get_academic_interests()`: User's academic interest tags
- `get_about_user()`: Biographical information
- `get_education()`: Educational background
- `get_groups()`: WordPress group memberships
- `get_activity()`: Recent user activity from WordPress
- `get_blog_posts()`: WordPress blog integration
- `works_deposits`: KC Works publications
- `mastodon_posts`: Social media feed integration

**Caching Strategy**
The API uses Django's `@cached_property` decorator for expensive operations:
- Profile data loading
- WordPress database queries
- External service calls (Mastodon)
- KC works processing

### Forms and Data Validation (`forms.py`)

#### ProfileForm Class

**Key Features**
- Comprehensive form covering all Profile model fields
- TinyMCE integration for rich text fields with sanitization
- Academic interests selection using Select2 widget
- Custom field processing for HTML content
- File upload support for CV documents

**Security Features**
- HTML sanitization through custom `SanitizedTinyMCE` widget
- Allowed HTML tags: `p`, `b`, `i`, `u`, `em`, `strong`, `a`, `ul`, `ol`, `li`, `br`, headers, tables, images
- Attribute filtering for links and images
- XSS protection through Django's built-in mechanisms

## Integration Points

### WordPress Integration

The app maintains extensive integration with WordPress/BuddyPress:

**Database Access**
- Read-only access to WordPress tables through Django models
- User synchronization between Django and WordPress systems
- Group membership and activity tracking
- Blog post integration and display

**Data Synchronization**
- Profile information synced between systems
- User authentication handled by CILogon integration
- WordPress user metadata access for extended profile fields

### External Services

**Mastodon Integration** (`mastodon.py`)
- Social media feed integration
- Profile verification and display
- Post fetching and caching
- Server-specific API handling

**KC Works Integration** (`works.py`)
- Publication and research output management
- Citation style formatting (configurable)
- Visibility controls for different work types
- Integration with external academic databases

### HTMX Integration

The app extensively uses HTMX for dynamic content loading:

**Benefits**
- Improved user experience with partial page updates
- Reduced server load through targeted content requests
- Progressive enhancement approach
- Seamless integration with Django templates

**Implementation**
- Dedicated HTMX endpoints for each content type
- Template fragments for partial rendering
- JavaScript-free dynamic interactions
- Graceful degradation for non-HTMX clients

## Configuration and Settings

### Citation Styles
- Configurable through `settings.CITATION_STYLES`
- Default style: "MHRA"
- Used for KC Works formatting
- User-selectable preference in profile settings

### Media Handling
- Profile images and cover images supported
- CV file uploads with validation
- WordPress media integration
- Configurable upload paths and restrictions

### Caching Strategy
- Redis-based caching for expensive operations
- Profile data caching with configurable timeouts
- WordPress query result caching
- External service response caching

## Development and Testing

### Key Files Structure
```
newprofile/
├── models.py          # Data models (Profile, COManage, WordPress)
├── views/             # Modular view organization
│   ├── health.py      # Health check endpoints
│   ├── home.py        # Home page views
│   ├── members.py     # Member directory views
│   ├── search.py      # Search functionality
│   ├── stats.py       # Statistics views
│   └── profile/       # Profile-specific views
├── urls.py            # URL routing configuration
├── forms.py           # Form definitions and validation
├── api.py             # API layer and data access
├── utils.py           # Utility functions
├── works.py           # KC Works integration
├── mastodon.py        # Social media integration
├── mailchimp.py       # Mailchimp newsletter integration
├── notifications.py   # Notification system
├── management/        # Django management commands
├── migrations/        # Database migrations
├── tests/             # Test suite
└── templatetags/      # Custom template tags
```

### CMS Pages Integration

The application includes a CMS system for configurable content pages:

**SitePage Model** (in `pages` app)
- Stores CMS-managed pages with title, slug, and body content
- Used for registration start page and terms of service
- Editable through Django admin

**Pre-configured Pages**:
- `registration-start`: Entry point for new user registration
- `terms-of-service`: Terms and conditions displayed during registration

### Testing Considerations
- WordPress database integration testing
- External service mocking (Mastodon)
- HTMX endpoint testing
- Form validation and security testing
- Profile visibility and privacy controls

### Performance Optimization
- Cached property usage for expensive operations
- Database query optimization
- HTMX for reduced page load times
- Strategic use of Django's caching framework

## Security Considerations

### Data Protection
- HTML sanitization in user-generated content
- XSS protection through template escaping
- File upload validation and restrictions
- Database query parameterization

### Privacy Controls
- Granular visibility settings for profile sections
- User-controlled data sharing preferences
- Integration with authentication system
- Secure handling of external service credentials

### WordPress Integration Security
- Read-only database access
- Parameterized queries for WordPress data
- Validation of WordPress user data
- Secure session handling between systems

## Troubleshooting

### Common Issues
1. **WordPress Database Connection**: Verify database settings and permissions
2. **Mastodon Integration**: Check API credentials and server accessibility
3. **Profile Image Loading**: Verify media file permissions and paths
4. **HTMX Endpoints**: Ensure proper URL configuration and view permissions
5. **Citation Formatting**: Validate citation style configuration

### Debugging Tools
- Django debug toolbar for query analysis
- Logging configuration for API calls
- Template debugging for HTMX responses
- Cache inspection for performance issues

### Performance Monitoring
- Database query monitoring
- External service response times
- Cache hit/miss ratios
- HTMX endpoint performance metrics
