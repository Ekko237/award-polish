const form = document.querySelector("#contact-form");
if (form) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = form.querySelector("#email").value.trim();
    const status = form.querySelector("#form-status");
    if (!email.includes("@") || !email.includes(".")) {
      status.textContent = "邮箱格式不对，请检查有没有漏写 @，比如 name@example.com";
      status.dataset.state = "error";
      return;
    }
    status.textContent = "谢谢你，我们会尽快回复。";
    status.dataset.state = "success";
  });
}
