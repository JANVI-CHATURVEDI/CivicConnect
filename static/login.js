const password = document.getElementById("id_password");
const togglePassword = document.getElementById("togglePassword");


// ================= PASSWORD SHOW / HIDE =================

if (togglePassword && password) {

    togglePassword.addEventListener("click", function () {

        const icon = togglePassword.querySelector("i");

        if (password.type === "password") {

            password.type = "text";
            icon.classList.remove("fa-eye");
            icon.classList.add("fa-eye-slash");
            togglePassword.setAttribute("aria-label", "Hide password");

        } else {

            password.type = "password";
            icon.classList.remove("fa-eye-slash");
            icon.classList.add("fa-eye");
            togglePassword.setAttribute("aria-label", "Show password");
        }

    });

}


// ================= GOOGLE LOGIN =================
// Not implemented in this build (would require django-allauth / OAuth
// credentials). Left as a clear placeholder rather than pretending it works.

const googleBtn = document.getElementById("googleBtn");

if (googleBtn) {

    googleBtn.addEventListener("click", function () {
        alert("Google Login is not enabled in this build. Please use your username and password.");
    });

}
