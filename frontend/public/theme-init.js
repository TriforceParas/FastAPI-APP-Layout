(function () {
  try {
    var t = localStorage.getItem("app_theme");
    if (t !== "light" && t !== "dark")
      t = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    document.documentElement.style.colorScheme = t;
  } catch (e) {}
})();
