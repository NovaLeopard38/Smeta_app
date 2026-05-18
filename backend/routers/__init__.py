# Smeta App Backend Routers
# Each router module handles a specific domain of the API.
#
# Architecture note: Due to the large size of the original monolithic app.py,
# the refactoring is being done incrementally. New endpoints should be added
# to the appropriate router module. Existing endpoints in app.py will be
# migrated progressively.
#
# Router modules:
# - auth.py: Authentication (login, register, me)
# - smetas.py: Smeta CRUD, items, revisions, export
# - materials.py: Material catalog, import, images
# - ai.py: AI assistant, recommendations, public chat
# - admin.py: User management, access control
# - voice.py: Voice calls (Tinkoff VoiceKit)
# - leads.py: Lead management, quotes
# - seo.py: SEO pages, sitemap, robots.txt
