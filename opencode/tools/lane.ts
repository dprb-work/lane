import { spawn } from "node:child_process";
import path from "node:path";

import { tool } from "@opencode-ai/plugin";

type ArgValue = boolean | string | null | undefined;

const REPO_ROOT = "__LANE_REPO_ROOT__";
const LANE = process.env.LANE_BIN || path.join(REPO_ROOT, ".venv", "bin", "lane");
const JSON_COMMANDS = new Set([
  "doctor",
  "finalize",
  "list",
  "push",
  "review",
  "status",
  "sync",
  "verify",
]);

function expandHome(raw: string): string {
  if (!raw.startsWith("~/")) return raw;
  const home = process.env.HOME;
  if (!home) return raw;
  return path.join(home, raw.slice(2));
}

function resolvePath(raw: string, directory: string): string {
  const expanded = expandHome(raw.trim());
  if (path.isAbsolute(expanded)) return path.normalize(expanded);
  return path.resolve(directory, expanded);
}

function option(flag: string, value: ArgValue): string[] {
  if (value === undefined || value === null || value === false) return [];
  if (value === true) return [flag];
  const trimmed = value.trim();
  return trimmed ? [flag, trimmed] : [];
}

function selector(raw: string | null | undefined, directory: string): string[] {
  if (!raw?.trim()) return [];
  const trimmed = raw.trim();
  if (trimmed === "." || trimmed.startsWith("./") || trimmed.startsWith("../") || trimmed.startsWith("~/") || path.isAbsolute(trimmed)) {
    return [resolvePath(trimmed, directory)];
  }
  return [trimmed];
}

async function runLane(
  args: string[],
  cwd: string,
  signal: AbortSignal,
): Promise<string> {
  return await new Promise((resolve, reject) => {
    const child = spawn(LANE, args, {
      cwd,
      signal,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        const output = stdout.trim();
        if (output) {
          resolve(output);
          return;
        }
        reject(new Error(stderr.trim() || `lane exited with code ${code}`));
        return;
      }
      resolve(stdout.trim());
    });
  });
}

const selectorField = tool.schema
  .string()
  .optional()
  .describe("Lane selector. Path-like values are resolved relative to the current OpenCode directory.");

const commandSchema = tool.schema.discriminatedUnion("name", [
  tool.schema.object({
    name: tool.schema.literal("init"),
    path: tool.schema.string().optional().describe("Repository path to initialize. Defaults to current directory."),
  }),
  tool.schema.object({
    name: tool.schema.literal("start"),
    branch: tool.schema.string().min(1).describe("Branch in <type>/<slug> form."),
    base: tool.schema.string().optional().describe("Base branch/ref. Defaults to main."),
  }),
  tool.schema.object({
    name: tool.schema.literal("status"),
    selector: selectorField,
  }),
  tool.schema.object({
    name: tool.schema.literal("list"),
  }),
  tool.schema.object({
    name: tool.schema.literal("doctor"),
    path: tool.schema
      .string()
      .optional()
      .describe("Repository or lane path to inspect. Defaults to current directory."),
  }),
  tool.schema.object({
    name: tool.schema.literal("verify"),
    selector: selectorField,
  }),
  tool.schema.object({
    name: tool.schema.literal("sync"),
    selector: selectorField,
  }),
  tool.schema.object({
    name: tool.schema.literal("review"),
    selector: selectorField,
    reviewAgent: tool.schema.array(tool.schema.string()).optional().describe("Paseo provider mode/review agent names."),
    reviewJudge: tool.schema.string().optional().describe("Paseo provider mode/review judge name."),
  }),
  tool.schema.object({
    name: tool.schema.literal("finalize"),
    selector: selectorField,
    noVerify: tool.schema
      .boolean()
      .optional()
      .describe("Reuse an already fresh verification result instead of rerunning."),
    forceWithLease: tool.schema
      .boolean()
      .optional()
      .describe("Push rewritten history with git push --force-with-lease."),
  }),
  tool.schema.object({
    name: tool.schema.literal("push"),
    selector: selectorField,
    noVerify: tool.schema
      .boolean()
      .optional()
      .describe("Reuse an already fresh verification result instead of rerunning."),
    forceWithLease: tool.schema
      .boolean()
      .optional()
      .describe("Push rewritten history with git push --force-with-lease."),
  }),
  tool.schema.object({
    name: tool.schema.literal("cleanup"),
    selector: selectorField,
    deleteRemoteBranch: tool.schema.boolean().optional().describe("Delete the remote branch after confirming the PR is merged."),
  }),
  tool.schema.object({
    name: tool.schema.literal("abort"),
    selector: selectorField,
    discard: tool.schema.boolean().optional().describe("Allow aborting with uncommitted changes present."),
    closePr: tool.schema.boolean().optional().describe("Close the associated PR during abort."),
    deleteRemoteBranch: tool.schema.boolean().optional().describe("Delete the remote branch during abort."),
  }),
  tool.schema.object({
    name: tool.schema.literal("raw"),
    argv: tool.schema
      .array(tool.schema.string())
      .min(1)
      .describe("Escape hatch for newly added lane CLI arguments. First item must be a lane subcommand."),
  }),
]);

function buildCommand(command: any, directory: string): string[] {
  let argv: string[];
  switch (command.name) {
    case "init":
      argv = ["init", ...(command.path ? [resolvePath(command.path, directory)] : [])];
      break;
    case "start":
      argv = ["start", command.branch, ...option("--base", command.base)];
      break;
    case "status":
      argv = ["status", ...selector(command.selector, directory)];
      break;
    case "list":
      argv = ["list"];
      break;
    case "doctor":
      argv = ["doctor", ...(command.path ? [resolvePath(command.path, directory)] : [])];
      break;
    case "verify":
      argv = ["verify", ...selector(command.selector, directory)];
      break;
    case "sync":
      argv = ["sync", ...selector(command.selector, directory)];
      break;
    case "review":
      argv = [
        "review",
        ...selector(command.selector, directory),
        ...(command.reviewAgent ?? []).flatMap((name: string) => option("--review-agent", name)),
        ...option("--review-judge", command.reviewJudge),
      ];
      break;
    case "finalize":
      argv = [
        "finalize",
        ...selector(command.selector, directory),
        ...option("--no-verify", command.noVerify),
        ...option("--force-with-lease", command.forceWithLease),
      ];
      break;
    case "push":
      argv = [
        "push",
        ...selector(command.selector, directory),
        ...option("--no-verify", command.noVerify),
        ...option("--force-with-lease", command.forceWithLease),
      ];
      break;
    case "cleanup":
      argv = ["cleanup", ...selector(command.selector, directory), ...option("--delete-remote-branch", command.deleteRemoteBranch)];
      break;
    case "abort":
      argv = [
        "abort",
        ...selector(command.selector, directory),
        ...option("--discard", command.discard),
        ...option("--close-pr", command.closePr),
        ...option("--delete-remote-branch", command.deleteRemoteBranch),
      ];
      break;
    case "raw":
      return command.argv;
  }

  return JSON_COMMANDS.has(command.name) ? [...argv, "--json"] : argv;
}

export default tool({
  description:
    "Run the Paseo-native lane CLI with typed arguments for init, start, status, list, doctor, verify, sync, review, push, finalize, cleanup, and abort.",
  args: {
    command: commandSchema.describe("Structured lane command to execute."),
  },
  async execute(args, context) {
    const command = buildCommand(args.command, context.directory);

    context.metadata({
      title: `lane ${args.command.name}`,
      metadata: { command: args.command.name },
    });

    const output = await runLane(command, context.directory, context.abort);
    return [`tool: lane`, `command: lane ${command.join(" ")}`, output].join("\n");
  },
});
