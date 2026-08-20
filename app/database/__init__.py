"""Datenbankpaket – re-exportiert alle öffentlichen Symbole für Rückwärtskompatibilität."""

from .core import (
    DB_PATH,
    DEFAULT_SETTINGS,
    DEFAULT_SEARCH_TERMS,
    get_db,
    init_db,
    utcnow,
)

from .settings import (
    get_settings,
    get_setting,
    set_setting,
    save_settings,
)

from .search_terms import (
    get_search_terms,
    add_search_term,
    delete_search_term,
    toggle_search_term,
    update_term_max_price,
)

from .listings import (
    is_dismissed,
    is_known_listing,
    dismiss_listing,
    save_listing,
    update_listing_distance,
    toggle_favorite,
    update_listing_note,
    find_duplicate_platform,
    get_distinct_platforms,
    get_platform_counts,
    get_listings,
    get_listing_count,
    get_listing_by_id,
    get_listings_today,
    get_unnotified_listings,
    claim_unnotified_listings,
    mark_listings_notified,
    clear_old_listings,
    clear_listings_older_than,
    clear_listings_by_platform,
    clear_all_listings,
    get_all_listing_urls,
    mark_listings_availability_checked,
    delete_listing_by_listing_id,
    cleanup_mismatched_listings,
)

from .geocache import (
    get_geocache,
    save_geocache,
    clear_geocache,
)

from .profiles import (
    get_profiles,
    get_profile,
    create_profile,
    update_profile,
    update_profile_notify,
    update_last_alert_sent,
    delete_profile,
    update_profile_last_seen,
)

from .stats import (
    log_crawl_run,
    log_notification,
    get_price_stats,
    get_system_stats,
)

__all__ = [
    # core
    "DB_PATH", "DEFAULT_SETTINGS", "DEFAULT_SEARCH_TERMS", "get_db", "init_db", "utcnow",
    # settings
    "get_settings", "get_setting", "set_setting", "save_settings",
    # search_terms
    "get_search_terms", "add_search_term", "delete_search_term",
    "toggle_search_term", "update_term_max_price",
    # listings
    "is_dismissed", "is_known_listing", "dismiss_listing", "save_listing", "update_listing_distance",
    "toggle_favorite", "update_listing_note", "find_duplicate_platform",
    "get_distinct_platforms", "get_platform_counts", "get_listings", "get_listing_count",
    "get_listing_by_id", "get_listings_today", "get_unnotified_listings",
    "claim_unnotified_listings", "mark_listings_notified",
    "clear_old_listings", "clear_listings_older_than", "clear_listings_by_platform", "clear_all_listings",
    "get_all_listing_urls", "mark_listings_availability_checked",
    "delete_listing_by_listing_id", "cleanup_mismatched_listings",
    # geocache
    "get_geocache", "save_geocache", "clear_geocache",
    # profiles
    "get_profiles", "get_profile", "create_profile", "update_profile",
    "update_profile_notify", "update_last_alert_sent", "delete_profile", "update_profile_last_seen",
    # stats
    "log_crawl_run", "log_notification", "get_price_stats", "get_system_stats",
]
