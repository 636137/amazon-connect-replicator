import cors from "cors";
import express from "express";

import { connectRouter } from "./routes/connect.js";

const app = express();
app.disable("x-powered-by");
app.use(cors());
app.use(express.json({ limit: "20mb" }));

app.get("/healthz", (_req, res) => {
  res.status(200).json({ ok: true });
});

app.use("/api/connect", connectRouter);

const port = Number(process.env.PORT || 3001);
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`API listening on http://localhost:${port}`);
});
