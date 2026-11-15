const form = document.querySelector('#world-form');
const input = document.querySelector('#seed');
const error = document.querySelector('#seed-error');

input.addEventListener('invalid', () => {
  error.textContent = 'Enter a whole number from 1 to 1,000,000.';
  input.setAttribute('aria-invalid', 'true');
});
input.addEventListener('input', () => {
  error.textContent = '';
  input.removeAttribute('aria-invalid');
});
form.addEventListener('submit', event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const value = Number(input.value);
  if (!Number.isInteger(value) || value < 1 || value > 1000000) return;
  location.href = `/world/${value}`;
});
