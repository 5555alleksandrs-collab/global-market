import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import "dotenv/config";

const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
const reminderCheckIntervalMs = Number(process.env.REMINDER_CHECK_INTERVAL_MS || 30000);
const telegramApiBase = telegramToken
  ? `https://api.telegram.org/bot${telegramToken}`
  : null;
const currentFile = fileURLToPath(import.meta.url);
const currentDir = path.dirname(currentFile);
const dataDir = path.join(currentDir, "data");
const dataFile = path.join(dataDir, "tasks.json");
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "short",
  timeStyle: "short",
});
const homeReplyMarkup = {
  keyboard: [
    [{ text: "Сегодня" }, { text: "Список" }],
    [{ text: "Помощь" }],
  ],
  resize_keyboard: true,
  input_field_placeholder: "Напиши задачу, например: завтра 19:00 купить молоко",
};

let offset = 0;
let store = { chats: {} };
let saveChain = Promise.resolve();
let reminderScanInProgress = false;

if (!telegramToken) {
  console.error("TELEGRAM_BOT_TOKEN is missing. Create a .env file or export the variable.");
  process.exit(1);
}

function createChatState() {
  return {
    nextTaskId: 1,
    tasks: [],
  };
}

function getChatState(chatId) {
  const key = String(chatId);
  if (!store.chats[key]) {
    store.chats[key] = createChatState();
  }

  return store.chats[key];
}

async function loadStore() {
  try {
    const raw = await readFile(dataFile, "utf8");
    const parsed = JSON.parse(raw);

    store = {
      chats: parsed?.chats && typeof parsed.chats === "object" ? parsed.chats : {},
    };
  } catch (error) {
    if (error.code !== "ENOENT") {
      console.error("Failed to read task storage, starting with an empty store:", error);
    }

    store = { chats: {} };
    await persistStore();
  }
}

async function persistStore() {
  const snapshot = `${JSON.stringify(store, null, 2)}\n`;

  saveChain = saveChain.then(async () => {
    await mkdir(dataDir, { recursive: true });
    await writeFile(dataFile, snapshot, "utf8");
  });

  return saveChain;
}

async function telegram(method, payload = {}) {
  const response = await fetch(`${telegramApiBase}/${method}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok || !data.ok) {
    throw new Error(data.description || `Telegram API error (${response.status})`);
  }

  return data.result;
}

function splitMessage(text, maxLength = 4000) {
  if (text.length <= maxLength) {
    return [text];
  }

  const parts = [];
  let start = 0;

  while (start < text.length) {
    let end = Math.min(start + maxLength, text.length);
    const breakpoint = text.lastIndexOf("\n", end);

    if (breakpoint > start + 200) {
      end = breakpoint;
    }

    parts.push(text.slice(start, end));
    start = end;
  }

  return parts;
}

async function sendText(chatId, text, extra = {}) {
  const chunks = splitMessage(text);

  for (const [index, chunk] of chunks.entries()) {
    await telegram("sendMessage", {
      chat_id: chatId,
      text: chunk,
      ...(index === chunks.length - 1 ? extra : {}),
    });
  }
}

function getCommand(text) {
  const match = text.match(/^\/([a-z_]+)(?:@\w+)?(?:\s+([\s\S]*))?$/i);

  if (!match) {
    return null;
  }

  return {
    name: match[1].toLowerCase(),
    args: (match[2] || "").trim(),
  };
}

function parseTaskId(raw) {
  const normalized = raw.trim().replace(/^#/, "");
  const value = Number(normalized);

  if (!Number.isInteger(value) || value <= 0) {
    return null;
  }

  return value;
}

function normalizeInput(text) {
  return text.trim().toLowerCase().replace(/\s+/g, " ");
}

function cleanupTaskText(text) {
  return text
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .trim();
}

function parseDateTime(raw) {
  const value = raw.trim();
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$/);

  if (!match) {
    return null;
  }

  const [, year, month, day, hour, minute] = match;
  const date = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
    0,
  );

  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day) ||
    date.getHours() !== Number(hour) ||
    date.getMinutes() !== Number(minute)
  ) {
    return null;
  }

  return date.toISOString();
}

function formatDateTime(value) {
  return dateTimeFormat.format(new Date(value));
}

function createDateTimeFromParts(year, month, day, hour, minute) {
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null;
  }

  const date = new Date(year, month - 1, day, hour, minute, 0, 0);

  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day ||
    date.getHours() !== hour ||
    date.getMinutes() !== minute
  ) {
    return null;
  }

  return date.toISOString();
}

function createRelativeDateTime(keyword, hour, minute) {
  const offsets = {
    "сегодня": 0,
    "завтра": 1,
    "послезавтра": 2,
  };

  if (!(keyword in offsets) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null;
  }

  const now = new Date();
  const date = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() + offsets[keyword],
    hour,
    minute,
    0,
    0,
  );

  return date.toISOString();
}

function createNearestDateTime(hour, minute) {
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null;
  }

  const now = new Date();
  const candidate = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    hour,
    minute,
    0,
    0,
  );

  if (candidate.getTime() <= now.getTime()) {
    candidate.setDate(candidate.getDate() + 1);
  }

  return candidate.toISOString();
}

function removeMatchedSlice(text, start, end) {
  return cleanupTaskText(`${text.slice(0, start)} ${text.slice(end)}`);
}

function extractDateTimeFromText(text) {
  const absoluteMatch = text.match(
    /\b(?:до|к|на|дедлайн)?\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})\b/i,
  );

  if (absoluteMatch && absoluteMatch.index !== undefined) {
    const [, year, month, day, hour, minute] = absoluteMatch;
    const iso = createDateTimeFromParts(
      Number(year),
      Number(month),
      Number(day),
      Number(hour),
      Number(minute),
    );

    if (iso) {
      return {
        iso,
        cleanedText: removeMatchedSlice(
          text,
          absoluteMatch.index,
          absoluteMatch.index + absoluteMatch[0].length,
        ),
      };
    }
  }

  const relativePatterns = [
    /\b(?:до|к|на)?\s*(сегодня|завтра|послезавтра)\s*(?:в\s*)?(\d{1,2})(?::(\d{2}))?\b/i,
    /\b(?:до|к|на)?\s*(?:в\s*)?(\d{1,2})(?::(\d{2}))?\s*(сегодня|завтра|послезавтра)\b/i,
  ];

  for (const pattern of relativePatterns) {
    const match = text.match(pattern);

    if (!match || match.index === undefined) {
      continue;
    }

    const keyword = Number.isNaN(Number(match[1])) ? match[1].toLowerCase() : match[3].toLowerCase();
    const hour = Number.isNaN(Number(match[1])) ? Number(match[2]) : Number(match[1]);
    const minute = Number.isNaN(Number(match[1])) ? Number(match[3] || "0") : Number(match[2] || "0");
    const iso = createRelativeDateTime(keyword, hour, minute);

    if (iso) {
      return {
        iso,
        cleanedText: removeMatchedSlice(text, match.index, match.index + match[0].length),
      };
    }
  }

  const timeOnlyMatch = text.match(/\bв\s*(\d{1,2}):(\d{2})\b/i);

  if (timeOnlyMatch && timeOnlyMatch.index !== undefined) {
    const iso = createNearestDateTime(
      Number(timeOnlyMatch[1]),
      Number(timeOnlyMatch[2]),
    );

    if (iso) {
      return {
        iso,
        cleanedText: removeMatchedSlice(
          text,
          timeOnlyMatch.index,
          timeOnlyMatch.index + timeOnlyMatch[0].length,
        ),
      };
    }
  }

  return null;
}

function findTask(chatId, taskId) {
  const chatState = getChatState(chatId);
  return chatState.tasks.find((task) => task.id === taskId) || null;
}

function getOpenTasks(chatId) {
  const chatState = getChatState(chatId);

  return chatState.tasks
    .filter((task) => !task.doneAt)
    .sort((left, right) => {
      const leftDeadline = left.deadlineAt ? Date.parse(left.deadlineAt) : Number.MAX_SAFE_INTEGER;
      const rightDeadline = right.deadlineAt ? Date.parse(right.deadlineAt) : Number.MAX_SAFE_INTEGER;

      if (leftDeadline !== rightDeadline) {
        return leftDeadline - rightDeadline;
      }

      return left.id - right.id;
    });
}

function isToday(dateValue) {
  const now = new Date();
  const target = new Date(dateValue);

  return (
    now.getFullYear() === target.getFullYear() &&
    now.getMonth() === target.getMonth() &&
    now.getDate() === target.getDate()
  );
}

function isOverdue(dateValue) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return new Date(dateValue) < startOfToday;
}

function buildTaskLine(task) {
  const details = [];

  if (task.deadlineAt && isOverdue(task.deadlineAt)) {
    details.push("просрочено");
  } else if (task.deadlineAt && isToday(task.deadlineAt)) {
    details.push("сегодня");
  }

  if (task.deadlineAt) {
    details.push(`дедлайн ${formatDateTime(task.deadlineAt)}`);
  }

  if (task.remindAt) {
    details.push(`напомнить ${formatDateTime(task.remindAt)}`);
  }

  return details.length > 0
    ? `#${task.id} ${task.title} (${details.join(", ")})`
    : `#${task.id} ${task.title}`;
}

function buildHelpText() {
  return [
    "Я личный планер в Telegram.",
    "",
    "Можно по-простому, без строгих команд:",
    "завтра 19:00 купить молоко",
    "напомни завтра 18:00 купить молоко",
    "сегодня",
    "список",
    "готово 3",
    "",
    "Команды:",
    "/add Купить молоко",
    "/add Купить молоко | 2026-03-18 19:00",
    "/add Купить молоко | 2026-03-18 19:00 | 2026-03-18 18:00",
    "/list",
    "/today",
    "/done 3",
    "/delete 3",
    "/deadline 3 2026-03-18 19:00",
    "/remind 3 2026-03-18 18:00",
    "",
    "Формат даты и времени: YYYY-MM-DD HH:mm",
    "Можно просто отправить текст без команды, и я добавлю его как задачу.",
  ].join("\n");
}

async function createTask(chatId, { title, deadlineAt = null, remindAt = null }) {
  const cleanedTitle = cleanupTaskText(title);

  if (!cleanedTitle) {
    return "Нужен текст задачи.";
  }

  if (deadlineAt && remindAt && Date.parse(remindAt) > Date.parse(deadlineAt)) {
    return "Напоминание должно быть не позже дедлайна.";
  }

  const chatState = getChatState(chatId);
  const task = {
    id: chatState.nextTaskId,
    title: cleanedTitle,
    createdAt: new Date().toISOString(),
    deadlineAt,
    remindAt,
    reminderSentAt: null,
    doneAt: null,
  };

  chatState.nextTaskId += 1;
  chatState.tasks.push(task);
  await persistStore();

  return `Добавил задачу:\n${buildTaskLine(task)}\n\nОтметить выполнение: /done ${task.id}`;
}

async function addTask(chatId, rawInput) {
  const [titlePart, deadlinePart, remindPart] = rawInput
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);

  if (!titlePart) {
    return "Нужен текст задачи. Пример:\n/add Купить молоко | 2026-03-18 19:00 | 2026-03-18 18:00";
  }

  const deadlineAt = deadlinePart ? parseDateTime(deadlinePart) : null;
  const remindAt = remindPart ? parseDateTime(remindPart) : null;

  if (deadlinePart && !deadlineAt) {
    return "Не смог разобрать дедлайн. Используй формат YYYY-MM-DD HH:mm";
  }

  if (remindPart && !remindAt) {
    return "Не смог разобрать напоминание. Используй формат YYYY-MM-DD HH:mm";
  }

  if (deadlineAt && remindAt && Date.parse(remindAt) > Date.parse(deadlineAt)) {
    return "Напоминание должно быть не позже дедлайна.";
  }

  return createTask(chatId, {
    title: titlePart,
    deadlineAt,
    remindAt,
  });
}

async function markTaskDone(chatId, rawId) {
  const taskId = parseTaskId(rawId);

  if (!taskId) {
    return "Укажи номер задачи. Пример: /done 3";
  }

  const task = findTask(chatId, taskId);
  if (!task) {
    return `Задача #${taskId} не найдена.`;
  }

  if (task.doneAt) {
    return `Задача #${taskId} уже отмечена как выполненная.`;
  }

  task.doneAt = new Date().toISOString();
  await persistStore();

  return `Готово:\n${buildTaskLine(task)}`;
}

async function deleteTask(chatId, rawId) {
  const taskId = parseTaskId(rawId);

  if (!taskId) {
    return "Укажи номер задачи. Пример: /delete 3";
  }

  const chatState = getChatState(chatId);
  const index = chatState.tasks.findIndex((task) => task.id === taskId);

  if (index === -1) {
    return `Задача #${taskId} не найдена.`;
  }

  const [task] = chatState.tasks.splice(index, 1);
  await persistStore();

  return `Удалил задачу #${task.id}: ${task.title}`;
}

async function setTaskDeadline(chatId, rawArgs) {
  const [rawId, ...rest] = rawArgs.split(/\s+/);
  const taskId = parseTaskId(rawId || "");
  const deadlineAt = parseDateTime(rest.join(" "));

  if (!taskId || !deadlineAt) {
    return "Используй команду так: /deadline 3 2026-03-18 19:00";
  }

  const task = findTask(chatId, taskId);
  if (!task) {
    return `Задача #${taskId} не найдена.`;
  }

  if (task.remindAt && Date.parse(task.remindAt) > Date.parse(deadlineAt)) {
    return "Сначала обнови напоминание: оно не может быть позже дедлайна.";
  }

  task.deadlineAt = deadlineAt;
  await persistStore();

  return `Обновил дедлайн:\n${buildTaskLine(task)}`;
}

async function setTaskReminder(chatId, rawArgs) {
  const [rawId, ...rest] = rawArgs.split(/\s+/);
  const taskId = parseTaskId(rawId || "");
  const remindAt = parseDateTime(rest.join(" "));

  if (!taskId || !remindAt) {
    return "Используй команду так: /remind 3 2026-03-18 18:00";
  }

  const task = findTask(chatId, taskId);
  if (!task) {
    return `Задача #${taskId} не найдена.`;
  }

  if (task.deadlineAt && Date.parse(remindAt) > Date.parse(task.deadlineAt)) {
    return "Напоминание должно быть не позже дедлайна.";
  }

  task.remindAt = remindAt;
  task.reminderSentAt = null;
  await persistStore();

  return `Напоминание обновлено:\n${buildTaskLine(task)}`;
}

function buildTaskList(chatId) {
  const tasks = getOpenTasks(chatId);

  if (tasks.length === 0) {
    return "Активных задач пока нет.";
  }

  const overdue = tasks.filter((task) => task.deadlineAt && isOverdue(task.deadlineAt));
  const today = tasks.filter(
    (task) => task.deadlineAt && !isOverdue(task.deadlineAt) && isToday(task.deadlineAt),
  );
  const upcoming = tasks.filter(
    (task) => task.deadlineAt && !isOverdue(task.deadlineAt) && !isToday(task.deadlineAt),
  );
  const someday = tasks.filter((task) => !task.deadlineAt);
  const lines = [];

  if (overdue.length > 0) {
    lines.push("Просрочено:");
    lines.push(...overdue.map(buildTaskLine));
  }

  if (today.length > 0) {
    if (lines.length > 0) {
      lines.push("");
    }
    lines.push("Сегодня:");
    lines.push(...today.map(buildTaskLine));
  }

  if (upcoming.length > 0) {
    if (lines.length > 0) {
      lines.push("");
    }
    lines.push("Дальше:");
    lines.push(...upcoming.map(buildTaskLine));
  }

  if (someday.length > 0) {
    if (lines.length > 0) {
      lines.push("");
    }
    lines.push("Без дедлайна:");
    lines.push(...someday.map(buildTaskLine));
  }

  return lines.join("\n");
}

function buildTodayList(chatId) {
  const tasks = getOpenTasks(chatId);
  const overdue = tasks.filter((task) => task.deadlineAt && isOverdue(task.deadlineAt));
  const today = tasks.filter((task) => task.deadlineAt && isToday(task.deadlineAt));

  if (overdue.length === 0 && today.length === 0) {
    return tasks.length === 0
      ? "Активных задач пока нет."
      : "На сегодня задач с дедлайном нет. Напиши \"список\", чтобы увидеть все активные задачи.";
  }

  const lines = [];

  if (overdue.length > 0) {
    lines.push("Просрочено:");
    lines.push(...overdue.map(buildTaskLine));
  }

  if (today.length > 0) {
    if (lines.length > 0) {
      lines.push("");
    }
    lines.push("Сегодня:");
    lines.push(...today.map(buildTaskLine));
  }

  return lines.join("\n");
}

function getTextShortcut(text) {
  const normalized = normalizeInput(text);

  if (["помощь", "help", "команды", "меню", "menu", "start"].includes(normalized)) {
    return { name: "help", args: "" };
  }

  if (["сегодня", "today"].includes(normalized)) {
    return { name: "today", args: "" };
  }

  if (["список", "дела", "задачи", "list"].includes(normalized)) {
    return { name: "list", args: "" };
  }

  const doneMatch = normalized.match(/^(?:done|готово|сделано|сделал)\s+#?(\d+)$/i);
  if (doneMatch) {
    return { name: "done", args: doneMatch[1] };
  }

  const deleteMatch = normalized.match(/^(?:delete|удали|удалить)\s+#?(\d+)$/i);
  if (deleteMatch) {
    return { name: "delete", args: deleteMatch[1] };
  }

  const deadlineMatch = normalized.match(/^(?:deadline|дедлайн)\s+#?(\d+)\s+(.+)$/i);
  if (deadlineMatch) {
    return { name: "deadline", args: `${deadlineMatch[1]} ${deadlineMatch[2]}` };
  }

  const remindMatch = normalized.match(/^(?:remind|напомни|напоминание)\s+#?(\d+)\s+(.+)$/i);
  if (remindMatch) {
    return { name: "remind", args: `${remindMatch[1]} ${remindMatch[2]}` };
  }

  return null;
}

function parseSmartTask(text) {
  const reminderIntent = text.match(/^\s*напомни(?:ть)?\s+([\s\S]+)$/i);

  if (reminderIntent) {
    const extracted = extractDateTimeFromText(reminderIntent[1]);

    if (!extracted) {
      return {
        error:
          "Чтобы поставить напоминание, напиши так: напомни завтра 18:00 купить молоко",
      };
    }

    if (!extracted.cleanedText) {
      return {
        error: "После времени нужен текст задачи. Пример: напомни завтра 18:00 купить молоко",
      };
    }

    return {
      title: extracted.cleanedText,
      remindAt: extracted.iso,
      deadlineAt: null,
    };
  }

  const extracted = extractDateTimeFromText(text);

  if (!extracted || !extracted.cleanedText) {
    return null;
  }

  return {
    title: extracted.cleanedText,
    deadlineAt: extracted.iso,
    remindAt: null,
  };
}

function buildReminderText(task) {
  const lines = [`Напоминание по задаче #${task.id}:`, task.title];

  if (task.deadlineAt) {
    lines.push(`Дедлайн: ${formatDateTime(task.deadlineAt)}`);
  }

  lines.push(`Отметить выполнение: /done ${task.id}`);
  return lines.join("\n");
}

async function processCommand(chatId, text) {
  const command = getCommand(text);

  if (command) {
    switch (command.name) {
      case "start":
      case "help":
        return buildHelpText();
      case "add":
        return addTask(chatId, command.args);
      case "list":
        return buildTaskList(chatId);
      case "today":
        return buildTodayList(chatId);
      case "done":
        return markTaskDone(chatId, command.args);
      case "delete":
        return deleteTask(chatId, command.args);
      case "deadline":
        return setTaskDeadline(chatId, command.args);
      case "remind":
        return setTaskReminder(chatId, command.args);
      default:
        return `Не знаю команду /${command.name}.\n\n${buildHelpText()}`;
    }
  }

  const shortcut = getTextShortcut(text);
  if (shortcut) {
    return processCommand(chatId, `/${shortcut.name} ${shortcut.args}`.trim());
  }

  const smartTask = parseSmartTask(text);
  if (smartTask?.error) {
    return smartTask.error;
  }

  if (smartTask) {
    return createTask(chatId, smartTask);
  }

  return addTask(chatId, text);
}

function shouldAttachHomeKeyboard(text) {
  const command = getCommand(text);
  if (command && ["start", "help"].includes(command.name)) {
    return true;
  }

  const shortcut = getTextShortcut(text);
  return Boolean(shortcut && ["help"].includes(shortcut.name));
}

async function handleMessage(message) {
  const chatId = message.chat?.id;
  const text = message.text?.trim();

  if (!chatId || !text) {
    return;
  }

  await telegram("sendChatAction", {
    chat_id: chatId,
    action: "typing",
  });

  try {
    const reply = await processCommand(chatId, text);
    await sendText(chatId, reply, shouldAttachHomeKeyboard(text) ? { reply_markup: homeReplyMarkup } : {});
  } catch (error) {
    console.error("Failed to process message:", error);
    await sendText(chatId, "Не получилось обработать команду. Попробуй еще раз.");
  }
}

async function runReminderScan() {
  if (reminderScanInProgress) {
    return;
  }

  reminderScanInProgress = true;

  try {
    const now = Date.now();

    for (const [chatId, chatState] of Object.entries(store.chats)) {
      for (const task of chatState.tasks) {
        if (task.doneAt || !task.remindAt || task.reminderSentAt) {
          continue;
        }

        if (Date.parse(task.remindAt) > now) {
          continue;
        }

        try {
          await sendText(chatId, buildReminderText(task));
          task.reminderSentAt = new Date().toISOString();
          await persistStore();
        } catch (error) {
          console.error(`Failed to send reminder for chat ${chatId}, task #${task.id}:`, error);
        }
      }
    }
  } finally {
    reminderScanInProgress = false;
  }
}

function startReminderLoop() {
  const timer = setInterval(() => {
    runReminderScan().catch((error) => {
      console.error("Reminder scan failed:", error);
    });
  }, reminderCheckIntervalMs);

  timer.unref?.();

  runReminderScan().catch((error) => {
    console.error("Initial reminder scan failed:", error);
  });
}

async function syncCommands() {
  await telegram("setMyCommands", {
    commands: [
      { command: "start", description: "подсказка по боту" },
      { command: "help", description: "список команд" },
      { command: "add", description: "добавить задачу" },
      { command: "list", description: "все активные задачи" },
      { command: "today", description: "задачи на сегодня" },
      { command: "done", description: "отметить задачу выполненной" },
      { command: "delete", description: "удалить задачу" },
      { command: "deadline", description: "поставить дедлайн" },
      { command: "remind", description: "поставить напоминание" },
    ],
  });
}

async function pollUpdates() {
  while (true) {
    try {
      const updates = await telegram("getUpdates", {
        offset,
        timeout: 30,
        allowed_updates: ["message"],
      });

      for (const update of updates) {
        offset = update.update_id + 1;
        await handleMessage(update.message);
      }
    } catch (error) {
      console.error("Polling failed:", error);
      await new Promise((resolve) => setTimeout(resolve, 3000));
    }
  }
}

async function start() {
  await loadStore();

  const me = await telegram("getMe");
  console.log(`Telegram planner bot @${me.username} is running`);

  await telegram("deleteWebhook", { drop_pending_updates: false });
  await syncCommands();
  startReminderLoop();
  await pollUpdates();
}

start().catch((error) => {
  console.error("Bot startup failed:", error);
  process.exit(1);
});
