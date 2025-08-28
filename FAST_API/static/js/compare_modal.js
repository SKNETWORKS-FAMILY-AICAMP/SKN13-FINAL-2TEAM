document.addEventListener("DOMContentLoaded", function() {
    const modalOverlay = document.querySelector(".modal-overlay");
    const closeButton = document.querySelector(".close-button");

    if (modalOverlay && closeButton) {
        // Function to hide the modal
        function hideCompareModal() {
            modalOverlay.style.display = "none";
        }

        // Close button click event
        closeButton.addEventListener("click", hideCompareModal);

        // Click outside modal content to close
        modalOverlay.addEventListener("click", function(event) {
            if (event.target === modalOverlay) {
                hideCompareModal();
            }
        });
    }
});