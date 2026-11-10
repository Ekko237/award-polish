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
    const [, m, d] = date.value.split('-');
    const time = form.querySelector('[name="time"]');
    const people = form.querySelector('[name="people"]').value;
    status.textContent = `已收到：${Number(m)} 月 ${Number(d)} 日 ${time ? time.value : ''}，${people} 位。我们会在 30 分钟内打电话确认。`;
    status.classList.add('ok');
  });
}
