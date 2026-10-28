jest.mock('pdfkit', () => class MockPDFDocument {
  constructor() {
    this.page = { width: 595 };
    this.textValues = [];
    global.reportDocument = this;
  }

  pipe() { return this; }
  rect() { return this; }
  fill() { return this; }
  fillAndStroke() { return this; }
  fillColor() { return this; }
  fontSize() { return this; }
  font() { return this; }
  text(value) {
    this.textValues.push(value);
    return this;
  }
  end() { return this; }
});

const { generatePdfReport } = require('../services/reportService');

describe('PDF report metric rendering', () => {
  afterEach(() => {
    delete global.reportDocument;
  });

  test('renders missing latency and cost as not available instead of zero', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      metrics_by_tier: {}
    }, response);

    expect(global.reportDocument.textValues).toContain(
      '• Optimal End-to-End Latency: Not available'
    );
    expect(global.reportDocument.textValues).toContain(
      '• Estimated Monthly Operating Cost: Not available'
    );
    expect(global.reportDocument.textValues).toContain('Not available');
    expect(global.reportDocument.textValues).not.toContain('INR 0');
  });

  test('preserves a real zero cost rather than treating it as missing', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      metrics_by_tier: {
        on_device: {
          latency_ms: { value: 0 },
          monthly_cost_inr: { value: 0 }
        }
      }
    }, response);

    expect(global.reportDocument.textValues).toContain(
      '• Optimal End-to-End Latency: 0 ms'
    );
    expect(global.reportDocument.textValues).toContain(
      '• Estimated Monthly Operating Cost: INR 0 / month'
    );
  });
});
