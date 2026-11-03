let registering = false;
const $ = (id) => document.getElementById(id);

// Already logged in? Go straight to the calendar.
fetch("/api/me").then((r) => { if (r.ok) location.href = "/dashboard"; });

$("switch").addEventListener("click", () => {
  registering = !registering;
  $("name-field").classList.toggle("hidden", !registering);
  $("submit").textContent = registering ? "Create account" : "Log in";
  $("switch-text").textContent = registering ? "Have an account?" : "New here?";
  $("switch").textContent = registering ? "Log in" : "Create an account";
  $("password").autocomplete = registering ? "new-password" : "current-password";
  $("error").textContent = "";
});

$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("error").textContent = "";
  const body = { username: $("username").value.trim(), password: $("password").value };
  if (registering) body.display_name = $("display_name").value.trim();
  try {
    await api("POST", registering ? "/api/register" : "/api/login", body);
    location.href = registering ? "/dashboard?new=1" : "/dashboard";
  } catch (err) {
    $("error").textContent = err.message;
  }
});
