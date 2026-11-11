// server.js — маленький HTTP-сервер без зависимостей. Запуск: npm start
// Нужен потому, что <script type="module"> не работает при открытии файла через file://
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, normalize, extname, sep } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
// Тот же файл уровня, что у Python-версии
const LEVEL_FILE = join(HERE, '..', 'pacman_hunt', 'data', 'level.json');
const PORT = Number(process.env.PORT) || 8080;
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  let file;
  if (url.pathname === '/') file = join(HERE, 'index.html');
  else if (url.pathname === '/level.json') file = LEVEL_FILE;
  else file = normalize(join(HERE, decodeURIComponent(url.pathname)));
  // не отдаём файлы вне папки проекта (защита от ../../)
  if (file !== LEVEL_FILE && !file.startsWith(HERE + sep)) {
    res.writeHead(403); res.end('Нельзя'); return;
  }
  try {
    const data = await readFile(file);
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Не найдено');
  }
});

server.listen(PORT, () => {
  console.log(`Pac-Man Hunt (JS) запущен: http://localhost:${PORT}`);
  console.log('Остановить: Ctrl+C');
});
