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

            togglePassword.setAttribute(
                "aria-label",
                "Hide password"
            );

        } else {

            password.type = "password";

            icon.classList.remove("fa-eye-slash");
            icon.classList.add("fa-eye");

            togglePassword.setAttribute(
                "aria-label",
                "Show password"
            );
        }

    });

}


// ================= FORGOT PASSWORD =================

const forgotPassword =
    document.getElementById("forgotPassword");

if (forgotPassword) {

    forgotPassword.addEventListener("click", function (event) {

        event.preventDefault();

        alert(
            "Password reset will be connected with the backend later."
        );

    });

}


// ================= GOOGLE LOGIN =================

const googleBtn =
    document.getElementById("googleBtn");

if (googleBtn) {

    googleBtn.addEventListener("click", function () {

        alert(
            "Google Login will be connected with the backend later."
        );

    });

}


// ================= REGISTER =================

const registerLink =
    document.getElementById("registerLink");

if (registerLink) {

    registerLink.addEventListener("click", function (event) {

        event.preventDefault();

        alert(
            "Registration page will be connected later."
        );

    });

}