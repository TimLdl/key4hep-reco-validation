document.addEventListener("DOMContentLoaded", () => {
    // Lightbox modal functionality for plot viewing
    const modal = document.createElement("div");
    modal.className = "modal";
    modal.innerHTML = '<img src="" alt="Enlarged Plot">';
    document.body.appendChild(modal);

    const modalImg = modal.querySelector("img");

    document.querySelectorAll(".plot-card-body img").forEach((img) => {
        img.addEventListener("click", () => {
            modalImg.src = img.src;
            modal.style.display = "flex";
        });
    });

    modal.addEventListener("click", () => {
        modal.style.display = "none";
    });
});