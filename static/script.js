// =====================================================
// CivicConnect AI
// Homepage Interactions
// =====================================================


// =====================================================
// REPORT ISSUE MODAL
// =====================================================

const reportModal = document.getElementById("reportModal");
const closeReport = document.getElementById("closeReport");


// All buttons that should open Report Issue

const reportButtons = document.querySelectorAll(
    ".report-btn,  .footer-report-btn"
);


// OPEN MODAL

reportButtons.forEach(button => {

    button.addEventListener("click", function (event) {

        event.preventDefault();

        if (reportModal) {

            reportModal.classList.add("active");

            document.body.style.overflow = "hidden";

        }

    });

});


// CLOSE MODAL

if (closeReport) {

    closeReport.addEventListener("click", function () {

        reportModal.classList.remove("active");

        document.body.style.overflow = "";

    });

}


// CLOSE WHEN CLICKING OUTSIDE

if (reportModal) {

    reportModal.addEventListener("click", function (event) {

        if (event.target === reportModal) {

            reportModal.classList.remove("active");

            document.body.style.overflow = "";

        }

    });

}


// CLOSE WITH ESC KEY

document.addEventListener("keydown", function (event) {

    if (event.key === "Escape" && reportModal) {

        reportModal.classList.remove("active");

        document.body.style.overflow = "";

    }

});


// =====================================================
// PHOTO PREVIEW
// =====================================================

const issuePhoto = document.getElementById("issuePhoto");
const photoPreview = document.getElementById("photoPreview");


if (issuePhoto && photoPreview) {

    issuePhoto.addEventListener("change", function () {

        photoPreview.innerHTML = "";

        const file = this.files[0];

        if (!file) {
            return;
        }


        if (!file.type.startsWith("image/")) {

            alert("Please select an image file.");

            this.value = "";

            return;

        }


        const image = document.createElement("img");

        image.src = URL.createObjectURL(file);

        image.alt = "Selected civic issue";

        photoPreview.appendChild(image);

    });

}


// =====================================================
// GPS LOCATION
// =====================================================

const getLocation = document.getElementById("getLocation");
const issueLocation = document.getElementById("issueLocation");


if (getLocation && issueLocation) {

    getLocation.addEventListener("click", function () {


        if (!navigator.geolocation) {

            alert(
                "Geolocation is not supported by your browser."
            );

            return;

        }


        getLocation.textContent = "Detecting...";

        getLocation.disabled = true;


        navigator.geolocation.getCurrentPosition(

            function (position) {

                const latitude =
                    position.coords.latitude;

                const longitude =
                    position.coords.longitude;


                issueLocation.value =
                    `Latitude: ${latitude.toFixed(5)}, ` +
                    `Longitude: ${longitude.toFixed(5)}`;


                getLocation.textContent = "✓ Detected";

                getLocation.disabled = false;

            },


            function () {

                alert(
                    "Unable to detect your location. " +
                    "Please allow location access."
                );


                getLocation.textContent =
                    "📍 Detect";

                getLocation.disabled = false;

            },

            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }

        );

    });

}


// =====================================================
// REPORT FORM SUBMISSION
// =====================================================

const reportForm =
    document.getElementById("reportForm");


if (reportForm) {

    reportForm.addEventListener(
        "submit",
        function (event) {

            event.preventDefault();


            const category =
                document.getElementById(
                    "issueCategory"
                ).value;


            const description =
                document.getElementById(
                    "issueDescription"
                ).value.trim();


            const location =
                document.getElementById(
                    "issueLocation"
                ).value;


            const photo =
                document.getElementById(
                    "issuePhoto"
                ).files[0];


            // VALIDATION

            if (!category) {

                alert(
                    "Please select an issue category."
                );

                return;

            }


            if (!description) {

                alert(
                    "Please describe the issue."
                );

                return;

            }


            if (!photo) {

                alert(
                    "Please upload a photo of the issue."
                );

                return;

            }


            if (!location) {

                alert(
                    "Please detect your location."
                );

                return;

            }


            // SUCCESS SCREEN

            const reportBox =
                document.querySelector(
                    ".report-box"
                );


            reportBox.innerHTML = `

                <div class="report-success">

                    <div class="report-success-icon">
                        ✅
                    </div>

                    <h3>
                        Report Submitted Successfully!
                    </h3>

                    <p>
                        Your civic issue has been recorded.
                        The concerned authority can review
                        the information and take action.
                    </p>

                    <button
                        type="button"
                        class="submit-report"
                        id="successClose"
                    >
                        Done
                    </button>

                </div>

            `;


            // CLOSE SUCCESS SCREEN

            document
                .getElementById("successClose")
                .addEventListener(
                    "click",
                    function () {

                        reportModal.classList.remove(
                            "active"
                        );

                        document.body.style.overflow = "";

                        location.reload();

                    }
                );

        }
    );

}


// =====================================================
// MOBILE MENU
// =====================================================

const menuToggle =
    document.querySelector(".menu-toggle");

const nav =
    document.querySelector("nav");


if (menuToggle && nav) {

    menuToggle.addEventListener(
        "click",
        function () {

            nav.classList.toggle(
                "mobile-open"
            );

        }
    );

}


// =====================================================
// HOW IT WORKS BUTTON
// =====================================================

const howItWorksButton =
    document.querySelector(".secondary-btn");


if (howItWorksButton) {

    howItWorksButton.addEventListener(
        "click",
        function () {

            const section =
                document.getElementById(
                    "how-it-works"
                );


            if (section) {

                section.scrollIntoView({
                    behavior: "smooth"
                });

            }

        }
    );

}


// =====================================================
// LOGIN BUTTON
// =====================================================

const loginButton =
    document.querySelector(".login-btn");


if (loginButton) {

    loginButton.addEventListener(
        "click",
        function () {

            alert(
                "Login functionality will be connected by the backend team."
            );

        }
    );

}

// ===============================
// CIVIC CONTRIBUTOR BUTTON
// ===============================

const contributorBtn = document.querySelector(".contributor-btn");

if (contributorBtn) {
    contributorBtn.addEventListener("click", function () {
        alert("Civic Contributor registration will be connected by the backend team.");
    });
}

// ===============================
// IMPACT STATISTICS COUNTER
// ===============================

const statNumbers = document.querySelectorAll(".stat-number");

const startCounters = () => {
    statNumbers.forEach(stat => {
        const target = Number(stat.dataset.target);
        const suffix = stat.dataset.suffix || "";

        let current = 0;
        const duration = 1800;
        const increment = target / (duration / 20);

        const updateCounter = () => {
            current += increment;

            if (current >= target) {
                current = target;
                stat.textContent =
                    target === 10000
                        ? "10K+"
                        : target === 8000
                        ? "8K+"
                        : target + suffix;
                return;
            }

            if (target >= 1000) {
                stat.textContent =
                    Math.floor(current / 1000) + "K+";
            } else {
                stat.textContent =
                    Math.floor(current) + suffix;
            }

            requestAnimationFrame(updateCounter);
        };

        updateCounter();
    });
};


// Start animation when Impact section appears
const impactSection = document.querySelector(".impact-section");

if (impactSection) {
    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    startCounters();
                    observer.unobserve(impactSection);
                }
            });
        },
        {
            threshold: 0.3
        }
    );

    observer.observe(impactSection);
}