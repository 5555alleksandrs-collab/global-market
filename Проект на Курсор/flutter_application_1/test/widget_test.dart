import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_application_1/app.dart';
import 'package:flutter_application_1/application/providers.dart';

void main() {
  testWidgets('приложение стартует и показывает главный экран', (WidgetTester tester) async {
    TestWidgetsFlutterBinding.ensureInitialized();
    SharedPreferences.setMockInitialValues({
      'app_session_v1': 'showroom',
      'user_profile_v1':
          '{"id":"app-showroom","name":"Showroom","phone":"","email":null,"addresses":[]}',
    });
    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
        ],
        child: const GlobalMarketApp(),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.textContaining('GLOBAL'), findsWidgets);
  });
}
