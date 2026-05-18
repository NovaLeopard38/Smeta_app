import React from "react";
import { Link } from "react-router-dom";
import { useThemeContext } from "../../context/ThemeContext";
import ShellSearch from "./ShellSearch";

const pageToPath = { smetas: "/smetas", prices: "/prices", assistant: "/assistant", admin: "/admin" };

function TopBar({
  currentUser,
  activePage,
  pageItems,
  currentPageMeta,
  handleLogout,
  previewSmeta,
  money,
  shellSearch,
  setShellSearch,
  shellSearchFocused,
  setShellSearchFocused,
  shellHasResults,
  smetaSearchResults,
  shellSearchSuggestions,
  handleShellSearchKeyDown,
  handleShellSmetaOpen,
  handleShellSuggestionOpen,
  handleShellSuggestionAdd,
  parentIdOf,
  isWorkMaterial,
}) {
  const { theme, toggleTheme } = useThemeContext();
  const userAvatar = (currentUser?.email || "db").split("@")[0].slice(0, 2).toUpperCase();

  return (
    <header className="topbar">
      <div className="topbar-breadcrumb">
        <span className="topbar-app">СметаПро</span>
        <span className="topbar-sep">/</span>
        <span className="topbar-page">{currentPageMeta?.label || "Рабочий стол"}</span>
        {currentUser?.email && <span className="topbar-user">{currentUser.email}</span>}
      </div>

      <nav className="topbar-tabs" aria-label="Разделы приложения">
        {pageItems.map(page => (
          <Link
            key={page.id}
            to={pageToPath[page.id] || "/smetas"}
            className={activePage === page.id ? "topbar-tab active" : "topbar-tab"}
            title={page.hint}
          >
            {page.label}
          </Link>
        ))}
      </nav>

      <ShellSearch
        shellSearch={shellSearch}
        setShellSearch={setShellSearch}
        shellSearchFocused={shellSearchFocused}
        setShellSearchFocused={setShellSearchFocused}
        shellHasResults={shellHasResults}
        smetaSearchResults={smetaSearchResults}
        shellSearchSuggestions={shellSearchSuggestions}
        handleShellSearchKeyDown={handleShellSearchKeyDown}
        handleShellSmetaOpen={handleShellSmetaOpen}
        handleShellSuggestionOpen={handleShellSuggestionOpen}
        handleShellSuggestionAdd={handleShellSuggestionAdd}
        parentIdOf={parentIdOf}
        isWorkMaterial={isWorkMaterial}
        money={money}
      />

      <div className="topbar-right">
        <div className="topbar-total">
          <span>Итого</span>
          <strong>{money(previewSmeta?.total || 0)}</strong>
        </div>
        <button
          className="icon-btn"
          onClick={toggleTheme}
          title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
        >
          {theme === "dark" ? "\u2600" : "\u263E"}
        </button>
        <button className="icon-btn" onClick={handleLogout} title="Выйти">
          {"\u238B"}
        </button>
        <div className="avatar">{userAvatar}</div>
      </div>
    </header>
  );
}

export default TopBar;
