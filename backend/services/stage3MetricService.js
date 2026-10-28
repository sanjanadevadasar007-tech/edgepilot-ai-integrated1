const fs = require("fs");
const path = require("path");

function readJson(filename) {
  const fullPath = path.join(
    __dirname,
    "..",
    "examples",
    filename
  );

  return JSON.parse(
    fs.readFileSync(fullPath, "utf8")
  );
}

function getMetricsForWorkload(workload) {
  const supportedProfile =
    workload.application_type === "smart_camera" &&
    workload.model_name === "mobilenet_v2" &&
    workload.target_device === "Samsung Galaxy S25 (Family)" &&
    workload.runtime === "tflite" &&
    workload.precision === "float";

  if (!supportedProfile) {
    return {
      metrics_by_tier: null,
      cost_curves: null,
      evidence_mode: "unavailable"
    };
  }

  return {
    metrics_by_tier: readJson(
      "stage6_pareto_tradeoff_metrics_DEMO.json"
    ),
    cost_curves: readJson(
      "stage6_cost_curves_DEMO.json"
    ),
    evidence_mode: "illustrative_estimates"
  };
}

module.exports = { getMetricsForWorkload };