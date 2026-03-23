// Sidebar toggle
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// Topbar date
function updateDate() {
  const el = document.getElementById('topbar-date');
  if (el) {
    const now = new Date();
    el.textContent = now.toLocaleDateString('en-ZA', {weekday:'short', day:'numeric', month:'short', year:'numeric'});
  }
}
updateDate();

// SOS count polling
function pollSOS() {
  fetch('/api/sos-count').then(r => r.json()).then(d => {
    const badge = document.getElementById('sos-count');
    if (badge) {
      badge.textContent = d.count;
      badge.style.display = d.count > 0 ? 'flex' : 'none';
    }
  }).catch(()=>{});
}
pollSOS();
setInterval(pollSOS, 30000);

// Tabs
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      const parent = btn.closest('.tab-container') || document;
      parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      parent.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = parent.querySelector(`#tab-${target}`);
      if (pane) pane.classList.add('active');
    });
  });
}
initTabs();

// Auto-dismiss flash messages
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => {
    f.style.transition = 'opacity 0.5s';
    f.style.opacity = '0';
    setTimeout(() => f.remove(), 500);
  });
}, 5000);

// Mood slider
const moodSlider = document.getElementById('mood-slider');
if (moodSlider) {
  const moodVal = document.getElementById('mood-value');
  const moodEmoji = document.getElementById('mood-emoji');
  const emojis = {1:'😭',2:'😢',3:'😞',4:'😟',5:'😐',6:'🙂',7:'😊',8:'😄',9:'😁',10:'🤩'};
  function updateMood() {
    const v = parseInt(moodSlider.value);
    if (moodVal) moodVal.textContent = v;
    if (moodEmoji) moodEmoji.textContent = emojis[v] || '';
  }
  moodSlider.addEventListener('input', updateMood);
  updateMood();
}

// Confirm delete
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm || 'Are you sure?')) e.preventDefault();
  });
});

// Like posts
document.querySelectorAll('.like-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const postId = btn.dataset.post;
    const res = await fetch(`/forum/post/${postId}/like`, {method:'POST'});
    const data = await res.json();
    btn.querySelector('.like-count').textContent = data.likes;
    btn.classList.add('liked');
  });
});

// Form validation
document.querySelectorAll('form[data-validate]').forEach(form => {
  form.addEventListener('submit', e => {
    let valid = true;
    form.querySelectorAll('[required]').forEach(input => {
      if (!input.value.trim()) {
        input.style.borderColor = '#e74c3c';
        valid = false;
      } else {
        input.style.borderColor = '';
      }
    });
    if (!valid) {
      e.preventDefault();
      const msg = form.querySelector('.validation-msg');
      if (msg) msg.style.display = 'block';
    }
  });
});

// Chart.js mood chart (loaded per page)
function renderMoodChart(labels, moodData, stressData, sleepData) {
  const ctx = document.getElementById('moodChart');
  if (!ctx) return;
  if (typeof Chart === 'undefined') return;
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Mood (1-10)',
          data: moodData,
          borderColor: '#003087',
          backgroundColor: 'rgba(0,48,135,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: '#003087',
        },
        {
          label: 'Stress (1-10)',
          data: stressData,
          borderColor: '#e74c3c',
          backgroundColor: 'rgba(231,76,60,0.05)',
          fill: false,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#e74c3c',
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { font: { family: 'DM Sans' }, boxWidth: 12 } },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        y: { min: 0, max: 10, grid: { color: '#f0f0f0' }, ticks: { font: { family: 'DM Sans', size: 11 } } },
        x: { grid: { display: false }, ticks: { font: { family: 'DM Sans', size: 11 } } }
      }
    }
  });
}
