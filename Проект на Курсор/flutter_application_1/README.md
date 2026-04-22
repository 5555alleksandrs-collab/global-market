# TechStore — MVP интернет-магазина техники (Flutter)

## Запуск

1. Установите [Flutter](https://docs.flutter.dev/get-started/install) (stable).
2. В корне проекта (папка `flutter_application_1`):

```bash
flutter pub get
```

3. Если папок `android/` и `ios/` ещё нет, сгенерируйте платформы:

```bash
flutter create .
```

4. Запуск на устройстве или эмуляторе:

```bash
flutter run
```

## Mock-авторизация

На экране кода введите **`1234`**.

## Админ-панель (локально на устройстве)

### Как открыть (скрытый вход)

На экране **Профиль** **удерживайте палец на карточке с аватаром ~2 секунды** — откроется ввод PIN.  
Пункт в настройках специально **убран**, чтобы случайные пользователи не находили админку.

### PIN

- Значение по умолчанию задано в коде: `lib/core/constants/admin_constants.dart` (`AdminConstants.defaultPin`).  
- После первого входа задайте свой PIN в **Админ → Система** (минимум 6 символов).  
- Для production нужны **сервер, роли и HTTPS** — текущая схема только для разработки.

### Разделы

- **Обзор** — статистика и быстрые действия.  
- **По категориям** — товары «папками» (как в магазине).  
- **Все товары** — полный список, поиск, удаление.  
- **Система** — смена PIN, сброс каталога, выход.

Данные каталога — **SharedPreferences** (`catalog_products_v1`).  
**Варианты** товара при правке из админки не меняются (как раньше).

## Где подключать API

| Назначение | Файлы / слой |
|------------|----------------|
| HTTP-клиент | `lib/core/network/dio_client.dart` — задайте `baseUrl`, заголовки, interceptors (токен). |
| Контракт данных | `lib/core/domain/repositories/catalog_repository.dart` — реализуйте, например, `ApiCatalogRepository` с `Dio`. |
| Подмена в DI | `lib/application/providers.dart` — замените `MockCatalogRepository()` на реализацию с API. |
| Баннеры | Сейчас `assets/mock/banners.json`; позже — эндпоинт + парсинг в тот же `BannerSlide`. |
| Заказы / оплата | `OrdersNotifier` + репозиторий заказов; checkout отправляет POST и сохраняет ответ. |

## Архитектура

- **Feature-first**: `lib/features/<feature>/` (экраны и UI).
- **Общее ядро**: `lib/core/` — тема, роутинг, модели, ошибки, сеть, хранилище.
- **Состояние**: Riverpod (`lib/application/providers.dart`).
- **Навигация**: `go_router` + `StatefulShellRoute` для нижней панели (`lib/core/router/app_router.dart`).
- **Локальные данные**: `shared_preferences` — корзина, избранное, сессия телефона, заказы (mock).

## Ассеты

- `assets/mock/banners.json` — слайдер на главной.

## Как менять внешний вид (самое нужное)

| Что поменять | Где править |
|--------------|-------------|
| Цвета фона, акцента, текста | `lib/core/constants/app_colors.dart` |
| Тени у карточек и нижней панели | `lib/core/constants/app_shadows.dart` |
| Шрифты, кнопки, поля ввода (общая тема) | `lib/core/theme/app_theme.dart` (шрифт **Inter** через `google_fonts`) |
| Вид карточки товара | `lib/common/widgets/product_card.dart` |
| Главная (баннер, категории, секции) | `lib/features/home/home_screen.dart` |
| Нижнее меню | `lib/features/main_shell.dart` |
| Экран целиком (каталог, корзина и т.д.) | `lib/features/<имя>/...` |

После правок: сохранить файл и выполнить hot reload в терминале (`r`) или перезапустить приложение.

Первый запуск с **Google Fonts** может на секунду подгрузить шрифт из сети — это нормально.
