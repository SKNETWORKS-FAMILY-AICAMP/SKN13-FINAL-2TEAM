document.addEventListener("DOMContentLoaded", function() {
    const scrollContainers = document.querySelectorAll(".scroll-container");

    scrollContainers.forEach(container => {
        const leftArrow = container.querySelector(".scroll-arrow.left");
        const rightArrow = container.querySelector(".scroll-arrow.right");
        const posters = container.querySelector(".row-posters");

        leftArrow.addEventListener("click", () => {
            posters.scrollLeft -= 300; // Adjust scroll distance as needed
        });

        rightArrow.addEventListener("click", () => {
            posters.scrollLeft += 300; // Adjust scroll distance as needed
        });
    });
});
