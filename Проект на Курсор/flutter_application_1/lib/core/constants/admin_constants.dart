/// Настройки доступа к админке (локально). Для production — сервер и роли.
abstract final class AdminConstants {
  /// Стартовый PIN, если вы ещё не задали свой в разделе «Система».
  /// После смены кода в приложении используется только сохранённый PIN.
  static const String defaultPin = '928471';

  /// Минимальная длина пользовательского PIN.
  static const int minPinLength = 6;
}
