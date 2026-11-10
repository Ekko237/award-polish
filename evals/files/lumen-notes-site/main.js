const banner = document.querySelector(".cookie-banner");
const acceptButton = document.querySelector("#cookie-accept");
if (banner && localStorage.getItem("lumen-consent") === "yes") banner.hidden = true;
if (acceptButton) {
  acceptButton.addEventListener("click", () => {
    localStorage.setItem("lumen-consent", "yes");
    banner.hidden = true;
  });
}

initAnalytics();
