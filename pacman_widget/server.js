// server.js — статический сервер без зависимостей. Запуск: npm start
// Почему нужен сервер: ES-модули (import) не работают при открытии файла через file://
// Корень сервера — папка репозитория, потому что виджет импортирует ядро из ../pacman_js
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, normalize, extname, sep, relative } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..'); // корень репозитория
const PORT = Number(process.env.PORT) || 8080;
// Отдаём ТОЛЬКО эти папки: секреты бота (py_bot/.env) наружу не попадут
const ALLOWED = ['pacman_widget', 'pacman_js', join('pacman_hunt', 'data')];
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/' || url.pathname === '/pacman_widget') { // корень -> страница виджета
    res.writeHead(302, { Location: '/pacman_widget/' });
    res.end();
    return;
  }
  let path = decodeURIComponent(url.pathname);
  if (path.endsWith('/')) path += 'index.html';
  const file = normalize(join(ROOT, path));
  const rel = relative(ROOT, file);
  const ok = ALLOWED.some((dir) => rel.startsWith(dir + sep));
  if (!ok) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Нельзя');
    return;
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

// Порт занят (например, уже запущен другой сервер) — понятное сообщение вместо падения
server.on('error', (e) => {
  if (e.code === 'EADDRINUSE') console.log(`Порт ${PORT} занят. Запустите так: PORT=8081 npm start`);
  else console.log(`Ошибка сервера: ${e.message}`);
  process.exit(1);
});

// 127.0.0.1 — сервер виден только с этого компьютера
server.listen(PORT, '127.0.0.1', () => {
  console.log(`Виджет Pac-Man Hunt: http://127.0.0.1:${PORT}/pacman_widget/`);
  console.log('Остановить: Ctrl+C');
});
