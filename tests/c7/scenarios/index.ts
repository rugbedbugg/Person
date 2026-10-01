/** The C7 behavioural scenario catalogue (ADR 0024). Frozen at the manifest. */
import type { Scenario } from "../scenario.ts";
import { rf1Food } from "./rf1-food.ts";

export const SCENARIOS: Scenario[] = [rf1Food];
