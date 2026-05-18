# Frontend Component Structure

This directory contains the planned component decomposition of the monolithic `App.jsx`.

## Migration Plan

The current `App.jsx` (~2000 lines) should be split into these components:

### Pages (full-page views)
- `pages/SmetaPage.jsx` — Main smeta editor view
- `pages/CatalogPage.jsx` — Materials catalog with search/filters
- `pages/AdminPage.jsx` — Admin panel (users, access)
- `pages/LoginPage.jsx` — Auth form (login/register)

### Components (reusable UI)
- `components/SmetaList.jsx` — Tree/list of smetas with selection
- `components/SmetaDetails.jsx` — Smeta metadata form (customer, tax, adjustments)
- `components/SmetaItems.jsx` — Table of smeta items with inline editing
- `components/MaterialCard.jsx` — Single material card in catalog
- `components/MaterialSearch.jsx` — Search bar with filters
- `components/AiChat.jsx` — AI command interface
- `components/Navigation.jsx` — Top nav bar / page switcher
- `components/ShareDialog.jsx` — Smeta sharing form
- `components/RevisionHistory.jsx` — Revision list with restore

### Hooks (shared logic)
- `hooks/useAuth.js` — Token management, login/logout
- `hooks/useApi.js` — Axios instance with interceptors
- `hooks/useSmetas.js` — Smeta CRUD operations
- `hooks/useMaterials.js` — Material search/pagination

## How to Migrate

1. Extract state and handlers from App.jsx into custom hooks
2. Create page components that compose smaller components
3. Move JSX sections from App.jsx to components one at a time
4. Keep App.jsx as a thin router (just switches pages)
5. Test after each extraction

## Current Status

The migration is planned but not yet executed to avoid breaking
the working application. Components can be extracted one at a time.
