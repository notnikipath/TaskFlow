import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 30,
  duration: "1m",
};

export default function () {
  const res = http.get("http://localhost:8280/health");
  check(res, { "status is 200": (r) => r.status === 200 });
  sleep(1);
}
