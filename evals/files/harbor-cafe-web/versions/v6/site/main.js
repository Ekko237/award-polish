// 预订表单
const form = document.querySelector('.booking-form');
if (form) {
  const status = form.querySelector('.form-status');
  const date = form.querySelector('input[name="date"]');
  const today = new Date();
  const iso = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  date.min = iso(today);
  form.addEventListener('submit', event => {
    event.preventDefault();
    status.textContent = '已提交，我们会尽快联系您。';
  });
}
