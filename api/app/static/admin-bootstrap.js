"use strict";

const form = document.getElementById("registration");
const capability = document.getElementById("capability");
const password = document.getElementById("password");
const username = document.getElementById("username");
const status = document.getElementById("status");
const submit = form.querySelector("button");

function clearSecrets() {
  capability.value = "";
  password.value = "";
}

window.addEventListener("pagehide", clearSecrets);
window.addEventListener("pageshow", clearSecrets);
form.addEventListener("invalid", () => {
  clearSecrets();
  status.textContent = "Check the input requirements, then enter the capability and password again.";
}, true);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submit.disabled = true;
  status.textContent = "Creating your administrator…";
  let payload = JSON.stringify({
    capability: capability.value,
    username: username.value,
    password: password.value,
  });
  clearSecrets();
  try {
    const pending = fetch("/api/v1/admin/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
    });
    payload = "";
    const response = await pending;
    if (response.ok) {
      form.remove();
      status.textContent = "Administrator created. Registration is now closed.";
      status.className = "success";
    } else if (response.status === 410) {
      form.remove();
      status.textContent = "Registration is already complete and is now closed.";
    } else if (response.status === 403) {
      status.textContent = "The capability is invalid or expired. Check it or issue a new one, then enter your password again.";
    } else if (response.status === 400) {
      status.textContent = "Check the input requirements, then enter the capability and password again.";
    } else {
      status.textContent = "Registration is unavailable. Check the server, then try again. Your secret fields have been cleared.";
    }
  } catch {
    status.textContent = "The response could not be confirmed. Reload to check whether registration is closed before trying again.";
  } finally {
    payload = "";
    clearSecrets();
    submit.disabled = false;
    status.focus();
  }
});
