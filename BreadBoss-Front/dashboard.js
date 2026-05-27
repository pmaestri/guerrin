/* ============================================================
   BreadBoss · Dashboard charts
   Conectado al agente de IA (breadboss-auditor Lambda)
   ============================================================ */

// ── ENDPOINT ───────────────────────────────────────────────────────────────────
const API_ENDPOINT = 'https://hvwo8db0c8.execute-api.us-east-1.amazonaws.com/auditor';

// ── PALETA ────────────────────────────────────────────────────────────────────
const palette = {
    ink:     '#2A1810',
    accent:  '#6B3E2C',
    accent2: '#A0664A',
    accent3: '#C99776',
    accent4: '#E0BFA0',
    soft:    '#EFE6D7',
    line:    '#D9CFC0',
    mute:    '#8A7866',
    ok:      '#5C7A4A',
    warn:    '#B4612A',
    danger:  '#8C2D1F',
};

// ── DEFAULTS CHART.JS ─────────────────────────────────────────────────────────
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size   = 11;
Chart.defaults.font.weight = '500';
Chart.defaults.color       = palette.mute;
Chart.defaults.borderColor = palette.line;

const baseScale = {
    grid:   { color: 'rgba(217,207,192,0.5)', drawBorder: false },
    ticks:  { color: palette.mute, font: { size: 10, weight: '500' } },
    border: { display: false },
};
const noLegend     = { legend: { display: false } };
const tooltipStyle = {
    backgroundColor: palette.ink,
    titleColor:      '#FFF',
    bodyColor:       palette.accent4,
    titleFont:       { size: 11, weight: '700' },
    bodyFont:        { size: 12, weight: '500' },
    padding:         12,
    cornerRadius:    4,
    displayColors:   false,
    borderColor:     palette.accent,
    borderWidth:     1,
};

// ── DATOS MOCK — misma estructura que retorna breadboss-auditor ───────────────
const MOCK_DATA = {
    fecha: '2026-05-25',
    resumen: 'El viernes a las 21:00 hs concentra el 14% del volumen semanal de pedidos, con un pico de ×5 sobre el promedio diario. Marketplaces (Rappi + PedidosYa) registra +27% en tiempo de entrega respecto a la app propia (28 min vs 22 min), lo que sugiere un cuello de botella en la coordinación con repartidores externos. El 6.2% de los pedidos fueron cancelados, concentrándose en falta de stock de "Sourdough Box" durante el pico. Se recomienda escalar la producción anticipada de los 3 ítems top entre las 19:00 y 20:30 hs y reforzar el equipo de packing los viernes.',
    metricas: {
        operacionales: {
            total_pedidos:              248,
            entregados:                 221,
            cancelados:                 16,
            tasa_cancelacion_pct:       6.2,
            tasa_incidencias_pct:       6.2,
            pedidos_por_hora:           { '09':8,'10':12,'11':22,'12':48,'13':67,'14':54,'15':28,'16':19,'17':23,'18':35,'19':58,'20':92,'21':124,'22':86,'23':41 },
            hora_pico:                  '21',
            pedidos_por_canal:          { 'App Mobile':104,'Web App':37,'WhatsApp Bot':47,'Rappi':38,'PedidosYa':22 },
            tiempo_promedio_global_min: 23,
            tiempo_max_min:             58,
            tiempo_promedio_por_canal:  { 'App Mobile':22,'Web App':24,'WhatsApp Bot':26,'Rappi':31,'PedidosYa':29 },
            tasa_cancelacion_por_canal: { 'App Mobile':3.1,'Web App':4.2,'WhatsApp Bot':5.8,'Rappi':8.4,'PedidosYa':7.2 },
            top_items: [
                { item: 'Sourdough Box',  cantidad: 184 },
                { item: 'Focaccia Combo', cantidad: 142 },
                { item: 'Pan de Campo',   cantidad: 118 },
                { item: 'Brioche Sweet',  cantidad: 96  },
                { item: 'Multigrain',     cantidad: 72  },
            ],
        },
        financieras: {
            revenue_total:     1847320,
            revenue_por_canal: { 'App Mobile':776677,'Marketplaces':572470,'WhatsApp Bot':314044,'Web App':184729 },
            ticket_promedio:   7430,
        },
        calidad: {
            pct_entregados_a_tiempo: 87,
            umbral_minutos:          45,
            pedidos_con_reclamo:     15,
            causas_cancelacion:      { 'sin stock':38,'cancelado por cliente':24,'falla técnica':14,'demora':16,'otro':8 },
        },
        tendencia: {
            disponible:           true,
            fecha_anterior:       '2026-05-18',
            pedidos_delta_pct:    28.0,
            revenue_delta_pct:    12.4,
            cancelados_delta_pct: -5.0,
            entregados_delta_pct: 30.0,
            total_anterior:       194,
            revenue_anterior:     1643200,
        },
    },
};

// ── HELPERS ───────────────────────────────────────────────────────────────────
const fmt = {
    money:   (v) => '$ ' + Number(v).toLocaleString('es-AR', { minimumFractionDigits: 0 }),
    pct:     (v) => (v > 0 ? '+' : '') + Number(v).toFixed(1) + '%',
    minutos: (v) => v + ' min',
};

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// Convierte objeto { canal: monto } a arrays de labels y porcentajes
function toLabelsAndPcts(obj) {
    const total  = Object.values(obj).reduce((a, b) => a + b, 0);
    const labels = Object.keys(obj);
    const pcts   = Object.values(obj).map(v => total > 0 ? Math.round(v / total * 100) : 0);
    return { labels, pcts, total };
}

// Registra instancias de Chart para poder destruirlas si se re-renderiza
const chartInstances = {};
function makeChart(id, config) {
    if (chartInstances[id]) chartInstances[id].destroy();
    chartInstances[id] = new Chart(document.getElementById(id), config);
}

// ── ACTUALIZAR KPIs Y TEXTO ───────────────────────────────────────────────────
function updateKPIs(op, fin, cal, tend, fecha, resumen) {
    // Agente IA
    const agentEl = document.querySelector('.agent-input');
    if (agentEl) agentEl.value = resumen || '';

    // Header KPIs
    setText('kpi-pedidos',       op.total_pedidos.toLocaleString('es-AR'));
    setText('kpi-pedidos-delta', tend.disponible ? fmt.pct(tend.pedidos_delta_pct) + ' vs semana ant.' : '');
    setText('kpi-entrega',       fmt.minutos(op.tiempo_promedio_global_min));
    setText('kpi-entrega-delta', tend.disponible ? fmt.pct(tend.entregados_delta_pct) + ' entregas' : '');
    setText('kpi-hora-pico',     op.hora_pico ? op.hora_pico + ':00 hs' : '—');
    setText('badge-hora-pico',   'PICO ' + (op.hora_pico || '—') + ':00');

    // Incidencias badge
    setText('badge-incidencias', op.tasa_incidencias_pct.toFixed(1) + '%');

    // Revenue
    setText('revenue-total',    fmt.money(fin.revenue_total));
    setText('ticket-promedio',  fmt.money(fin.ticket_promedio));
    setText('pedidos-pagados',  op.entregados.toLocaleString('es-AR'));
    setText('tasa-cancelacion', op.tasa_cancelacion_pct.toFixed(1) + '%');

    if (tend.disponible) {
        setText('revenue-delta',
            fmt.pct(tend.revenue_delta_pct) + ' vs semana ant. · ' +
            fmt.pct(tend.pedidos_delta_pct) + ' en pedidos'
        );
    }

    // Calidad badge
    setText('badge-on-time',      cal.pct_entregados_a_tiempo.toFixed(0) + '%');
    setText('card-sub-on-time',   'Pedidos entregados < ' + cal.umbral_minutos + ' min');

    // Tendencia badge
    if (tend.disponible) {
        setText('badge-tendencia-pedidos', fmt.pct(tend.pedidos_delta_pct));
    }
}

// ── CHARTS ────────────────────────────────────────────────────────────────────

/* 1. Pedidos por hora */
function renderOrdersByHour(op) {
    const horas  = Object.keys(op.pedidos_por_hora).sort();
    const counts = horas.map(h => op.pedidos_por_hora[h]);
    const pico   = op.hora_pico;

    makeChart('ordersByHour', {
        type: 'bar',
        data: {
            labels: horas,
            datasets: [{
                label: 'Pedidos',
                data:  counts,
                backgroundColor: (ctx) => {
                    const hora = horas[ctx.dataIndex];
                    if (hora === pico) return palette.accent;
                    return ctx.raw >= 60 ? palette.accent2 : palette.accent3;
                },
                borderRadius:  3,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { ...noLegend, tooltip: tooltipStyle },
            scales: {
                x: { ...baseScale, grid: { display: false } },
                y: { ...baseScale, beginAtZero: true },
            },
        },
    });
}

/* 2. Tiempo promedio de entrega por canal */
function renderDeliveryByChannel(op) {
    const labels = Object.keys(op.tiempo_promedio_por_canal);
    const data   = Object.values(op.tiempo_promedio_por_canal);
    const maxVal = Math.max(...data);

    makeChart('deliveryByChannel', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Minutos',
                data,
                backgroundColor: data.map(v =>
                    v === maxVal ? palette.warn : v > 25 ? palette.accent2 : palette.accent3
                ),
                borderRadius: 3, borderSkipped: false, barThickness: 22,
            }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                ...noLegend,
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} min` } },
            },
            scales: {
                x: { ...baseScale, beginAtZero: true, ticks: { ...baseScale.ticks, callback: (v) => v + ' min' } },
                y: { ...baseScale, grid: { display: false } },
            },
        },
    });
}

/* 3. Cancelación por canal */
function renderCancelByChannel(op) {
    const labels = Object.keys(op.tasa_cancelacion_por_canal);
    const data   = Object.values(op.tasa_cancelacion_por_canal);
    const maxVal = Math.max(...data);

    makeChart('cancelByChannel', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: data.map(v => v === maxVal ? palette.warn : palette.accent3),
                borderRadius: 3, borderSkipped: false,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                ...noLegend,
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw}%` } },
            },
            scales: {
                x: { ...baseScale, grid: { display: false } },
                y: { ...baseScale, beginAtZero: true, ticks: { ...baseScale.ticks, callback: (v) => v + '%' } },
            },
        },
    });
}

/* 4. Tasa de incidencias (donut) */
function renderIncidenceRate(op) {
    const pct = op.tasa_incidencias_pct;
    makeChart('incidenceRate', {
        type: 'doughnut',
        data: {
            labels: ['Con incidencia', 'Sin incidencia'],
            datasets: [{
                data: [pct, 100 - pct],
                backgroundColor: [palette.warn, palette.accent4],
                borderColor: palette.soft, borderWidth: 4,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '72%',
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 12 } },
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } },
            },
        },
    });
}

/* 5. Top ítems */
function renderTopItems(op) {
    const items    = op.top_items.slice(0, 5);
    const labels   = items.map(i => i.item);
    const data     = items.map(i => i.cantidad);

    makeChart('topItems', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: palette.accent,
                borderRadius: 3, borderSkipped: false, barThickness: 14,
            }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                ...noLegend,
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} unidades` } },
            },
            scales: {
                x: { ...baseScale, beginAtZero: true },
                y: { ...baseScale, grid: { display: false } },
            },
        },
    });
}

/* 6. Revenue por canal (donut) — convierte montos a % */
function renderRevenueByChannel(fin) {
    const { labels, pcts } = toLabelsAndPcts(fin.revenue_por_canal);

    makeChart('revenueByChannel', {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: pcts,
                backgroundColor: [palette.accent, palette.accent2, palette.accent3, palette.accent4],
                borderColor: palette.soft, borderWidth: 4,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '60%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: { boxWidth: 8, boxHeight: 8, font: { size: 11 }, padding: 14, color: palette.ink },
                },
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } },
            },
        },
    });
}

/* 7. Entregas a tiempo (donut) */
function renderOnTimeRate(cal) {
    const pct = cal.pct_entregados_a_tiempo;
    makeChart('onTimeRate', {
        type: 'doughnut',
        data: {
            labels: ['A tiempo', 'Demorados'],
            datasets: [{
                data: [pct, 100 - pct],
                backgroundColor: [palette.ok, palette.accent4],
                borderColor: palette.soft, borderWidth: 4,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '78%',
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 10 } },
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}%` } },
            },
        },
    });
}

/* 8. Reclamos por tipo — el Lambda no desglosa por tipo, se mantiene mock */
function renderComplaints() {
    makeChart('complaints', {
        type: 'bar',
        data: {
            labels: ['Demora', 'Item faltante', 'Mal estado', 'Cobro', 'Otro'],
            datasets: [{
                data: [42, 24, 16, 12, 6],
                backgroundColor: [palette.warn, palette.accent2, palette.accent3, palette.accent3, palette.accent4],
                borderRadius: 3, borderSkipped: false,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                ...noLegend,
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} reclamos` } },
            },
            scales: {
                x: { ...baseScale, grid: { display: false } },
                y: { ...baseScale, beginAtZero: true },
            },
        },
    });
}

/* 9. Causas de cancelación — viene de calidad.causas_cancelacion */
function renderCancelReasons(cal) {
    const labels = Object.keys(cal.causas_cancelacion);
    const data   = Object.values(cal.causas_cancelacion);

    makeChart('cancelReasons', {
        type: 'polarArea',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: [
                    'rgba(107,62,44,0.85)',
                    'rgba(160,102,74,0.85)',
                    'rgba(201,151,118,0.85)',
                    'rgba(180,97,42,0.85)',
                    'rgba(224,191,160,0.85)',
                ],
                borderColor: palette.soft, borderWidth: 2,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 8 } },
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.label}: ${c.raw}` } },
            },
            scales: {
                r: {
                    grid: { color: 'rgba(217,207,192,0.6)' },
                    ticks: { display: false },
                    angleLines: { color: 'rgba(217,207,192,0.6)' },
                },
            },
        },
    });
}

/* 10. Hoy vs semana anterior — usa pedidos_por_hora de hoy y escala para semana ant. */
function renderWeekCompare(op, tend) {
    const horas   = ['09','11','13','15','17','19','21','23'];
    const hoy     = horas.map(h => op.pedidos_por_hora[h] || 0);

    // Aproxima la semana anterior escalando la distribución de hoy
    const scale   = tend.disponible && op.total_pedidos > 0
        ? tend.total_anterior / op.total_pedidos
        : 0.78;
    const semAnt  = hoy.map(v => Math.round(v * scale));

    makeChart('weekCompare', {
        type: 'line',
        data: {
            labels: horas,
            datasets: [
                {
                    label: 'Hoy',
                    data:  hoy,
                    borderColor:     palette.accent,
                    backgroundColor: 'rgba(107,62,44,0.12)',
                    borderWidth: 2.5, fill: true, tension: 0.35,
                    pointRadius: 3, pointBackgroundColor: palette.accent,
                },
                {
                    label: 'Semana anterior',
                    data:  semAnt,
                    borderColor: palette.accent3,
                    borderDash:  [5, 4],
                    borderWidth: 2, fill: false, tension: 0.35,
                    pointRadius: 2, pointBackgroundColor: palette.accent3,
                },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top', align: 'end',
                    labels: { boxWidth: 14, boxHeight: 2, font: { size: 11 }, padding: 14, color: palette.ink },
                },
                tooltip: tooltipStyle,
            },
            scales: {
                x: { ...baseScale, grid: { display: false } },
                y: { ...baseScale, beginAtZero: true },
            },
        },
    });
}

/* 11. Evolución tiempo de entrega 30d — no hay datos históricos en el Lambda, se mantiene mock */
function renderDeliveryTrend() {
    const last30         = Array.from({ length: 30 }, (_, i) => i + 1);
    const deliverySeries = [28,29,27,28,30,29,28,27,26,27,26,25,26,25,24,25,24,25,24,23,24,23,22,23,22,23,22,23,22,23];

    makeChart('deliveryTrend', {
        type: 'line',
        data: {
            labels: last30,
            datasets: [{
                label: 'Min. promedio',
                data:  deliverySeries,
                borderColor:     palette.accent,
                backgroundColor: 'rgba(107,62,44,0.10)',
                borderWidth: 2.5, fill: true, tension: 0.4,
                pointRadius: 0, pointHoverRadius: 4,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { ...noLegend, tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw} min` } } },
            scales: {
                x: {
                    ...baseScale, grid: { display: false },
                    ticks: { ...baseScale.ticks, callback: (v, i) => i % 5 === 0 ? `D${last30[i]}` : '' },
                },
                y: { ...baseScale, beginAtZero: false, ticks: { ...baseScale.ticks, callback: (v) => v + ' min' } },
            },
        },
    });
}

/* 12. Canales crecimiento vs decrecimiento — no hay datos mensuales en el Lambda, se mantiene mock */
function renderChannelTrend() {
    makeChart('channelTrend', {
        type: 'bar',
        data: {
            labels: ['APP MOBILE', 'WHATSAPP BOT', 'PEDIDOSYA', 'WEB APP', 'RAPPI'],
            datasets: [{
                label: 'Variación mes vs mes',
                data:  [18.4, 22.7, 8.2, -3.1, -11.6],
                backgroundColor: (ctx) => ctx.raw >= 0 ? palette.ok : palette.danger,
                borderRadius: 3, borderSkipped: false, barThickness: 28,
            }],
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                ...noLegend,
                tooltip: { ...tooltipStyle, callbacks: { label: (c) => `${c.raw > 0 ? '+' : ''}${c.raw}%` } },
            },
            scales: {
                x: {
                    ...baseScale,
                    ticks:  { ...baseScale.ticks, callback: (v) => (v > 0 ? '+' : '') + v + '%' },
                    grid:   { color: 'rgba(217,207,192,0.5)' },
                },
                y: { ...baseScale, grid: { display: false } },
            },
        },
    });
}

// ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
function renderDashboard(data) {
    const { metricas, resumen, fecha } = data;
    const op   = metricas.operacionales;
    const fin  = metricas.financieras;
    const cal  = metricas.calidad;
    const tend = metricas.tendencia;

    updateKPIs(op, fin, cal, tend, fecha, resumen);

    renderOrdersByHour(op);
    renderDeliveryByChannel(op);
    renderCancelByChannel(op);
    renderIncidenceRate(op);
    renderTopItems(op);
    renderRevenueByChannel(fin);
    renderOnTimeRate(cal);
    renderComplaints();
    renderCancelReasons(cal);
    renderWeekCompare(op, tend);
    renderDeliveryTrend();
    renderChannelTrend();
}

// ── INDICADOR DE FUENTE DE DATOS ──────────────────────────────────────────────
function setDataSourceBanner(isLive, detail = '') {
    const dot  = document.getElementById('data-source-dot');
    const text = document.getElementById('data-source-text');
    if (!dot || !text) return;
    if (isLive) {
        dot.style.background  = '#5C7A4A';
        text.style.color      = '#5C7A4A';
        text.textContent      = '● LIVE — datos reales desde AWS' + (detail ? ' · ' + detail : '');
    } else {
        dot.style.background  = '#B4612A';
        text.style.color      = '#B4612A';
        text.textContent      = '● MOCK — datos de ejemplo' + (detail ? ' · ' + detail : '');
    }
}

// ── FETCH CON FALLBACK A MOCK ──────────────────────────────────────────────────
async function fetchDashboard(fecha = null) {
    if (API_ENDPOINT) {
        try {
            const url = fecha ? `${API_ENDPOINT}?fecha=${fecha}` : API_ENDPOINT;
            const res = await fetch(url);
            const raw = await res.json();

            // 404 = Lambda activo pero aún no hay pedidos para hoy
            if (res.status === 404) {
                const msg = raw.body || 'Sin pedidos para hoy todavía';
                console.info('[BreadBoss] Lambda respondió 404:', msg);
                setDataSourceBanner(false, 'Sin datos para hoy — el auditor corre a las 23:59 UTC');
                renderDashboard(MOCK_DATA);
                return;
            }

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            // API Gateway puede envolver el body como string
            const data = raw.body ? JSON.parse(raw.body) : raw;
            renderDashboard(data);
            setDataSourceBanner(true, data.fecha || '');
            return;
        } catch (e) {
            console.warn('[BreadBoss] API no disponible, usando datos mock:', e.message);
            setDataSourceBanner(false, e.message);
        }
    } else {
        setDataSourceBanner(false, 'API_ENDPOINT no configurado');
    }
    renderDashboard(MOCK_DATA);
}

// ── AUTH ──────────────────────────────────────────────────────────────────────
BB_AUTH.requireAuth();
document.getElementById('emailPill').textContent = BB_AUTH.getEmail() || '';
document.getElementById('logoutBtn').addEventListener('click', () => BB_AUTH.logout());

// ── SELECTOR DE FECHA ─────────────────────────────────────────────────────────
function cargarFecha() {
    const picker = document.getElementById('fecha-picker');
    const fecha  = picker ? picker.value : null;
    fetchDashboard(fecha || null);
}

// Setear fecha de hoy en el picker al cargar
(function initPicker() {
    const picker = document.getElementById('fecha-picker');
    if (picker) picker.value = new Date().toISOString().slice(0, 10);
})();

fetchDashboard();
