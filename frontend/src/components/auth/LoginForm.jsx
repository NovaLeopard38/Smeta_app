import React from "react";
import { useAuthContext } from "../../context/AuthContext";

function LoginForm({ onLogin, onRegister, message, error }) {
  const { loginForm, setLoginForm, authMode, setAuthMode } = useAuthContext();

  return (
    <main className="login-shell">
      <section className="panel login-panel">
        <p className="eyebrow">Сметный рабочий стол</p>
        <h1>Вход</h1>
        {(message || error) && (
          <div className={error ? "notice error" : "notice"}>
            {error || message}
          </div>
        )}
        <input
          type="email"
          placeholder="Email"
          value={loginForm.email}
          onChange={e => setLoginForm(current => ({ ...current, email: e.target.value }))}
        />
        <input
          type="password"
          placeholder="Пароль"
          value={loginForm.password}
          onChange={e => setLoginForm(current => ({ ...current, password: e.target.value }))}
          onKeyDown={e => {
            if (e.key === "Enter") {
              onLogin();
            }
          }}
        />
        <button onClick={authMode === "login" ? onLogin : onRegister}>
          {authMode === "login" ? "Войти" : "Зарегистрироваться"}
        </button>
        <button className="ghost" onClick={() => setAuthMode(current => current === "login" ? "register" : "login")}>
          {authMode === "login" ? "Нужна регистрация" : "Уже есть аккаунт"}
        </button>
        {authMode === "register" && (
          <p className="muted">
            После регистрации вы сразу войдёте в систему. Админский email недоступен для регистрации.
          </p>
        )}
      </section>
    </main>
  );
}

export default LoginForm;
