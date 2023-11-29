const RECORD_STATUS = Object.freeze({
  PENDING: "PENDING",
  DISCARDED: "DISCARDED",
  SUBMITTED: "SUBMITTED",
  DRAFT: "DRAFT",
});

const RECORD_STATUS_COLOR = Object.freeze({
  PENDING: "#bb720a",
  DISCARDED: "#c3c1c1",
  SUBMITTED: "#3e5cc9",
  DRAFT: "coral",
});

export { RECORD_STATUS, RECORD_STATUS_COLOR };
