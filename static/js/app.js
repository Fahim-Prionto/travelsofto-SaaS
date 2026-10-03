/**
 * ViserTrip Platform Core JavaScript Helpers
 */

document.addEventListener('DOMContentLoaded', function () {
  // Mobile Sidebar Toggle Handler
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('show');
    });
  }

  // Auto-dismiss alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });
});

// Chart.js helper with elegant theme colors
window.initViserChart = function (ctx, type, data, options = {}) {
  if (!window.Chart || !ctx) return null;

  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          font: { family: 'Plus Jakarta Sans', weight: '600', size: 12 },
          usePointStyle: true,
          padding: 15
        }
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleFont: { family: 'Plus Jakarta Sans', weight: '700' },
        bodyFont: { family: 'Plus Jakarta Sans' },
        padding: 12,
        cornerRadius: 8,
      }
    },
    scales: type !== 'pie' && type !== 'doughnut' ? {
      x: { grid: { display: false }, ticks: { font: { family: 'Plus Jakarta Sans' } } },
      y: { grid: { color: '#f1f5f9' }, ticks: { font: { family: 'Plus Jakarta Sans' } } }
    } : {}
  };

  return new Chart(ctx, {
    type: type,
    data: data,
    options: { ...defaultOptions, ...options }
  });
};
