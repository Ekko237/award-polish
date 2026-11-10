const form = document.querySelector("#contact-form");
if (form) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = form.querySelector("#email").value.trim();
    const status = form.querySelector("#form-status");
    if (!email.includes("@") || !email.includes(".")) {
      status.textContent = "提交失败";
      status.dataset.state = "error";
      return;
    }
    status.textContent = "谢谢你，我们会尽快回复。";
    status.dataset.state = "success";
  });
}
