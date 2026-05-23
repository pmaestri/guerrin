/* ============================================================
   BreadBoss · Dashboard charts
   Datos mockeados — reemplazar por endpoint real cuando aplique
   ============================================================ */

const palette = {
    ink:      '#2A1810',
    accent:   '#6B3E2C',
    accent2:  '#A0664A',
    accent3:  '#C99776',
    accent4:  '#E0BFA0',
    soft:     '#EFE6D7',
    line:     '#D9CFC0',
    mute:     '#8A7866',
    ok:       '#5C7A4A',
    warn:     '#B4612A',
    danger:   '#8C2D1F',
};

// Defaults globales
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.font.weight = '500';
Chart.defaults.color = palette.mute;
Chart.defaults.borderColor = palette.line;

const baseScale = {
    grid:   { color: 'rgba(217,207,192,0.5)', drawBorder: false },
    ticks:  { color: palette.mute, font: { size: 10, weight: '500' } },
    border: { display: false },
};

const noLegend = { legend: { display: false } };

const tooltipStyle = {
    backgroundColor: palette.ink,
    titleColor: '#FFF',
    bodyColor: palette.accent4,
    titleFont: { size: 11, weight: '700' },
    bodyFont: { size: 12, weight: '500' },
    padding: 12,
    cornerRadius: 4,
    displayColors: false,
    borderColor: palette.accent,
    borderWidth: 1,
};

/* ------------------------------------------------------------
   1. Pedidos por hora
   ------------------------------------------------------------ */
new Chart(document.getElementById('ordersByHour'), {
    type: 'bar',
    data: {
        labels: ['09','10','11','12','13','14','15','16','17','18','19','20','21','22','23'],
        datasets: [{
            label: 'Pedidos',
            data: [8, 12, 22, 48, 67, 54, 28, 19, 23, 35, 58, 92, 124, 86, 41],
            backgroundColor: (ctx) => {
                const v = ctx.raw;
                if (v >= 100) return palette.accent;
                if (v >= 60)  return palette.accent2;
                return palette.accent3;
            },
            borderRadius: 3,
            borderSkipped: false,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { ...noLegend, tooltip: tooltipStyle },
        scales: {
            x: { ...baseScale, grid: { display: false } },
            y: { ...baseScale, beginAtZero: true },
        }
    }
});

/* ------------------------------------------------------------
   2. Tiempo promedio de entrega por canal
   ------------------------------------------------------------ */
new Chart(document.getElementById('deliveryByChannel'), {
    type: 'bar',
    data: {
        labels: ['APP MOBILE', 'WEB APP', 'WHATSAPP BOT', 'RAPPI', 'PEDIDOSYA'],
        datasets: [{
            label: 'Minutos',
            data: [22, 24, 26, 31, 29],
            backgroundColor: [palette.accent2, palette.accent2, palette.accent3, palette.warn, palette.accent],
            borderRadius: 3,
            borderSkipped: false,
            barThickness: 22,
        }]
    },
    options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            ...noLegend,
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} min` } }
        },
        scales: {
            x: { ...baseScale, beginAtZero: true, ticks: { ...baseScale.ticks, callback: (v) => v + ' min' } },
            y: { ...baseScale, grid: { display: false } },
        }
    }
});

/* ------------------------------------------------------------
   3. Cancelación por canal
   ------------------------------------------------------------ */
new Chart(document.getElementById('cancelByChannel'), {
    type: 'bar',
    data: {
        labels: ['APP', 'WEB', 'WA BOT', 'MARKETPL.'],
        datasets: [{
            data: [3.1, 4.2, 5.8, 8.4],
            backgroundColor: [palette.accent3, palette.accent3, palette.accent2, palette.warn],
            borderRadius: 3,
            borderSkipped: false,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            ...noLegend,
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw}%` } }
        },
        scales: {
            x: { ...baseScale, grid: { display: false } },
            y: { ...baseScale, beginAtZero: true, ticks: { ...baseScale.ticks, callback: (v) => v + '%' } },
        }
    }
});

/* ------------------------------------------------------------
   4. Tasa de incidencias (donut)
   ------------------------------------------------------------ */
new Chart(document.getElementById('incidenceRate'), {
    type: 'doughnut',
    data: {
        labels: ['Con incidencia', 'Sin incidencia'],
        datasets: [{
            data: [6.2, 93.8],
            backgroundColor: [palette.warn, palette.accent4],
            borderColor: palette.soft,
            borderWidth: 4,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 12 } },
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } }
        }
    }
});

/* ------------------------------------------------------------
   5. Top ítems
   ------------------------------------------------------------ */
new Chart(document.getElementById('topItems'), {
    type: 'bar',
    data: {
        labels: ['Sourdough Box', 'Focaccia Combo', 'Pan de Campo', 'Brioche Sweet', 'Multigrain'],
        datasets: [{
            data: [184, 142, 118, 96, 72],
            backgroundColor: palette.accent,
            borderRadius: 3,
            borderSkipped: false,
            barThickness: 14,
        }]
    },
    options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { ...noLegend, tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} unidades` } } },
        scales: {
            x: { ...baseScale, beginAtZero: true },
            y: { ...baseScale, grid: { display: false } },
        }
    }
});

/* ------------------------------------------------------------
   6. Revenue por canal (donut)
   ------------------------------------------------------------ */
new Chart(document.getElementById('revenueByChannel'), {
    type: 'doughnut',
    data: {
        labels: ['App Mobile', 'Marketplaces', 'WhatsApp Bot', 'Web App'],
        datasets: [{
            data: [42, 31, 17, 10],
            backgroundColor: [palette.accent, palette.accent2, palette.accent3, palette.accent4],
            borderColor: palette.soft,
            borderWidth: 4,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '60%',
        plugins: {
            legend: {
                position: 'right',
                labels: { boxWidth: 8, boxHeight: 8, font: { size: 11 }, padding: 14, color: palette.ink }
            },
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } }
        }
    }
});

/* ------------------------------------------------------------
   7. On-time rate (donut)
   ------------------------------------------------------------ */
new Chart(document.getElementById('onTimeRate'), {
    type: 'doughnut',
    data: {
        labels: ['A tiempo', 'Demorados'],
        datasets: [{
            data: [87, 13],
            backgroundColor: [palette.ok, palette.accent4],
            borderColor: palette.soft,
            borderWidth: 4,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '78%',
        plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 10 } },
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } }
        }
    }
});

/* ------------------------------------------------------------
   8. Reclamos del cliente
   ------------------------------------------------------------ */
new Chart(document.getElementById('complaints'), {
    type: 'bar',
    data: {
        labels: ['Demora', 'Item faltante', 'Mal estado', 'Cobro', 'Otro'],
        datasets: [{
            data: [42, 24, 16, 12, 6],
            backgroundColor: [palette.warn, palette.accent2, palette.accent3, palette.accent3, palette.accent4],
            borderRadius: 3,
            borderSkipped: false,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { ...noLegend, tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} reclamos` } } },
        scales: {
            x: { ...baseScale, grid: { display: false } },
            y: { ...baseScale, beginAtZero: true },
        }
    }
});

/* ------------------------------------------------------------
   9. Causas de cancelación
   ------------------------------------------------------------ */
new Chart(document.getElementById('cancelReasons'), {
    type: 'polarArea',
    data: {
        labels: ['Sin stock', 'Cliente canceló', 'Error técnico', 'Demora repartidor', 'Dirección errónea'],
        datasets: [{
            data: [38, 24, 14, 16, 8],
            backgroundColor: [
                'rgba(107,62,44,0.85)',
                'rgba(160,102,74,0.85)',
                'rgba(201,151,118,0.85)',
                'rgba(180,97,42,0.85)',
                'rgba(224,191,160,0.85)',
            ],
            borderColor: palette.soft,
            borderWidth: 2,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 8 } },
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } }
        },
        scales: {
            r: {
                grid: { color: 'rgba(217,207,192,0.6)' },
                ticks: { display: false },
                angleLines: { color: 'rgba(217,207,192,0.6)' },
            }
        }
    }
});

/* ------------------------------------------------------------
   10. Hoy vs misma semana anterior
   ------------------------------------------------------------ */
new Chart(document.getElementById('weekCompare'), {
    type: 'line',
    data: {
        labels: ['09','11','13','15','17','19','21','23'],
        datasets: [
            {
                label: 'Hoy',
                data: [8, 22, 67, 28, 23, 58, 124, 41],
                borderColor: palette.accent,
                backgroundColor: 'rgba(107,62,44,0.12)',
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 3,
                pointBackgroundColor: palette.accent,
            },
            {
                label: 'Semana anterior',
                data: [6, 18, 52, 24, 18, 44, 96, 32],
                borderColor: palette.accent3,
                borderDash: [5, 4],
                borderWidth: 2,
                fill: false,
                tension: 0.35,
                pointRadius: 2,
                pointBackgroundColor: palette.accent3,
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top', align: 'end', labels: { boxWidth: 14, boxHeight: 2, font: { size: 11 }, padding: 14, color: palette.ink } },
            tooltip: tooltipStyle,
        },
        scales: {
            x: { ...baseScale, grid: { display: false } },
            y: { ...baseScale, beginAtZero: true },
        }
    }
});

/* ------------------------------------------------------------
   11. Evolución del tiempo de entrega — 30 días
   ------------------------------------------------------------ */
const last30 = Array.from({ length: 30 }, (_, i) => i + 1);
const deliverySeries = [28,29,27,28,30,29,28,27,26,27,26,25,26,25,24,25,24,25,24,23,24,23,22,23,22,23,22,23,22,23];

new Chart(document.getElementById('deliveryTrend'), {
    type: 'line',
    data: {
        labels: last30,
        datasets: [{
            label: 'Min. promedio',
            data: deliverySeries,
            borderColor: palette.accent,
            backgroundColor: 'rgba(107,62,44,0.10)',
            borderWidth: 2.5,
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { ...noLegend, tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} min` } } },
        scales: {
            x: { ...baseScale, grid: { display: false }, ticks: { ...baseScale.ticks, callback: (v, i) => i % 5 === 0 ? `D${last30[i]}` : '' } },
            y: { ...baseScale, beginAtZero: false, ticks: { ...baseScale.ticks, callback: (v) => v + ' min' } },
        }
    }
});

/* ------------------------------------------------------------
   12. Canales en crecimiento vs decrecimiento
   ------------------------------------------------------------ */
new Chart(document.getElementById('channelTrend'), {
    type: 'bar',
    data: {
        labels: ['APP MOBILE', 'WHATSAPP BOT', 'PEDIDOSYA', 'WEB APP', 'RAPPI'],
        datasets: [{
            label: 'Variación mes vs mes',
            data: [18.4, 22.7, 8.2, -3.1, -11.6],
            backgroundColor: (ctx) => ctx.raw >= 0 ? palette.ok : palette.danger,
            borderRadius: 3,
            borderSkipped: false,
            barThickness: 28,
        }]
    },
    options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            ...noLegend,
            tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw > 0 ? '+' : ''}${c.raw}%` } }
        },
        scales: {
            x: {
                ...baseScale,
                ticks: { ...baseScale.ticks, callback: (v) => (v > 0 ? '+' : '') + v + '%' },
                grid: { color: 'rgba(217,207,192,0.5)' }
            },
            y: { ...baseScale, grid: { display: false } },
        }
    }
});
