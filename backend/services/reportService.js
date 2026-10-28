// services/reportService.js
const PDFDocument = require('pdfkit');

function getMetricValue(metric) {
  const value = metric && typeof metric === 'object' ? metric.value : metric;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatMetric(value) {
  return value === null ? 'Not available' : value.toLocaleString('en-IN');
}

function generatePdfReport(data, res) {
  const doc = new PDFDocument({ margin: 35, size: 'A4' });

  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', 'attachment; filename="EdgePilot_Architecture_Report.pdf"');

  doc.pipe(res);

  // --- HEADER BAND ---
  doc.rect(0, 0, doc.page.width, 65).fill('#0F172A');

  doc.fillColor('#FFFFFF')
     .fontSize(18)
     .font('Helvetica-Bold')
     .text('EdgePilot Architecture & Metric Report', 35, 18);

  const genDate = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  doc.fontSize(8)
     .font('Helvetica')
     .fillColor('#94A3B8')
     .text(`Generated on: ${genDate} | Stage 3 Audit Compliant`, 35, 42);

  // --- WORKLOAD SPECIFICATIONS ---
  const workload = data.workload || {};
  doc.rect(35, 75, 525, 50).fillAndStroke('#F8FAFC', '#CBD5E1');

  doc.fillColor('#0F172A').fontSize(9).font('Helvetica-Bold').text('WORKLOAD SPECIFICATIONS', 45, 82);
  doc.fontSize(8).font('Helvetica').fillColor('#334155');
  doc.text(`Model: ${workload.model_name || 'N/A'}`, 45, 98);
  doc.text(`Latency SLA: ${workload.latency_requirement_ms || 'N/A'} ms`, 175, 98);
  doc.text(`Throughput: ${workload.expected_qps || 'N/A'} QPS`, 310, 98);
  doc.text(`RAM: ${workload.device_available_ram_mb || 'N/A'} MB`, 430, 98);

  // --- RECOMMENDED TIER BANNER ---
  const recTier = (data.recommended_tier || 'ON_DEVICE').toUpperCase();
  doc.rect(35, 135, 525, 40).fill('#1E40AF');

  doc.fillColor('#FFFFFF').fontSize(8).font('Helvetica-Bold').text('RECOMMENDED DEPLOYMENT TIER', 45, 142);
  doc.fontSize(14).font('Helvetica-Bold').text(recTier, 45, 154);

  // --- SECTION 1: STAGE 3 SUMMARY ---
  doc.fillColor('#0F172A').fontSize(11).font('Helvetica-Bold').text('1. Infrastructure Economics & Grounding Summary', 35, 190);
  doc.rect(35, 203, 525, 1).fill('#CBD5E1');

  const metrics = data.metrics_by_tier || {};
  const recKey = (data.recommended_tier || 'on_device').toLowerCase();
  const recData = metrics[recKey] || {};

  const recLat = getMetricValue(recData.latency_ms);
  const recCost = getMetricValue(recData.monthly_cost_inr);

  doc.fillColor('#334155').fontSize(9).font('Helvetica');
  doc.text(`• Optimal End-to-End Latency: ${formatMetric(recLat)}${recLat === null ? '' : ' ms'}`, 45, 212);
  doc.text(`• Estimated Monthly Operating Cost: ${recCost === null ? 'Not available' : `INR ${formatMetric(recCost)} / month`}`, 45, 226);

  // --- SECTION 2: STAGE 3 METRIC PROVENANCE TABLE ---
  doc.fillColor('#0F172A').fontSize(11).font('Helvetica-Bold').text('2. Stage 3 Metric Provenance Audit Matrix', 35, 250);
  doc.rect(35, 263, 525, 1).fill('#CBD5E1');

  let yPos = 272;

  // Header Row
  doc.rect(35, yPos, 525, 18).fill('#E2E8F0');
  doc.fillColor('#0F172A').fontSize(8).font('Helvetica-Bold');
  doc.text('TIER', 42, yPos + 5);
  doc.text('LATENCY (MS)', 130, yPos + 5);
  doc.text('MONTHLY COST', 210, yPos + 5);
  doc.text('SOURCE / REFERENCE', 310, yPos + 5);
  doc.text('METHOD', 440, yPos + 5);

  yPos += 18;

  const tiers = ['on_device', 'far_edge', 'regional_edge', 'cloud'];

  tiers.forEach((tKey) => {
    const tData = metrics[tKey] || {};

    const latObj = tData.latency_ms;
    const latVal = formatMetric(getMetricValue(latObj));
    const latSrc = latObj && typeof latObj === 'object'
      ? (latObj.source_reference || latObj.source || 'N/A')
      : 'N/A';

    const costObj = tData.monthly_cost_inr;
    const costValue = getMetricValue(costObj);
    const costMethod = costObj && typeof costObj === 'object' ? (costObj.method || 'N/A') : 'N/A';

    const isSelected = tKey === recKey;
    doc.rect(35, yPos, 525, 20).fill(isSelected ? '#DBEAFE' : (yPos % 2 === 0 ? '#FFFFFF' : '#F8FAFC'));

    doc.fillColor('#0F172A').fontSize(8).font('Helvetica-Bold');
    doc.text(tKey.replace('_', ' ').toUpperCase(), 42, yPos + 5);

    doc.font('Helvetica').fillColor('#334155');
    doc.text(`${latVal}${latVal === 'Not available' ? '' : ' ms'}`, 130, yPos + 5);
    doc.text(costValue === null ? 'Not available' : `INR ${formatMetric(costValue)}`, 210, yPos + 5);
    doc.text(`${latSrc}`, 310, yPos + 5, { width: 125 });
    doc.text(`${costMethod}`, 440, yPos + 5, { width: 115 });

    yPos += 20;
  });

  // --- SECTION 3: DETAILED COMPONENT BREAKDOWN ---
  yPos += 15;
  doc.fillColor('#0F172A').fontSize(11).font('Helvetica-Bold').text('3. Detailed Component Breakdown (Selected Tier)', 35, yPos);
  doc.rect(35, yPos + 13, 525, 1).fill('#CBD5E1');

  yPos += 22;

  const latComp = recData.latency_ms && typeof recData.latency_ms === 'object'
    ? (recData.latency_ms.latency_components_ms || {})
    : {};
  const costComp = recData.monthly_cost_inr && typeof recData.monthly_cost_inr === 'object'
    ? (recData.monthly_cost_inr.cost_components_inr || {})
    : {};

  doc.fillColor('#1E293B').fontSize(8).font('Helvetica-Bold').text('Latency Components (ms):', 45, yPos);
  yPos += 12;
  doc.font('Helvetica').fillColor('#475569');
  let latText = Object.entries(latComp).map(([k, v]) => `${k}: ${v}ms`).join(' | ') || 'N/A';
  doc.text(latText, 45, yPos, { width: 505 });

  yPos += 20;
  doc.fillColor('#1E293B').fontSize(8).font('Helvetica-Bold').text('Cost Components (INR):', 45, yPos);
  yPos += 12;
  doc.font('Helvetica').fillColor('#475569');
  let costText = Object.entries(costComp).map(([k, v]) => `${k}: INR ${v}`).join(' | ') || 'N/A';
  doc.text(costText, 45, yPos, { width: 505 });

  // Footer
  doc.rect(35, 780, 525, 1).fill('#CBD5E1');
  doc.fillColor('#94A3B8').fontSize(8).text('Confidential — EdgePilot System Automated Stage 3 Report', 35, 788, { align: 'center' });

  doc.end();
}

module.exports = { generatePdfReport };
