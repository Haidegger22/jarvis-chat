# 🗼 Jarvis Chat

Чат с ИИ-агентами **Джарвисом** 🤖 и **Пятницей** 💚

## Доступ

| Ссылка | Описание |
|--------|----------|
| [jarvis-chat.org](https://jarvis-chat.org) | Основной сайт через Cloudflare Tunnel |
| [GitHub Pages](https://haidegger22.github.io/jarvis-chat/) | Запасной вход (пароль тот же) |

## Состав
- `index.html` — фронтенд для GitHub Pages (с паролем + Bearer auth)
- `chat-server.py` — сервер (авторизация: Cookie + Bearer)

## Защита
- Двойной пароль: на странице (SHA256) и на сервере
- Bearer-токен для кросс-доменных запросов
