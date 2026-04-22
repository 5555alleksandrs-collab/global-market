import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../domain/models/product.dart';
import 'mock/mock_catalog_seed.dart';

/// Каталог в локальном хранилище (JSON). При первом запуске — копия mock seed.
class LocalCatalogStorage {
  LocalCatalogStorage(this._prefs);

  final SharedPreferences _prefs;

  static const _key = 'catalog_products_v1';

  Future<List<Product>> load() async {
    final raw = _prefs.getString(_key);
    if (raw == null || raw.isEmpty) {
      try {
        final imported = await rootBundle.loadString('assets/catalog/imported_products.json');
        final list = jsonDecode(imported) as List<dynamic>;
        final products =
            list.map((e) => Product.fromJson(e as Map<String, dynamic>)).toList();
        await save(products);
        return products;
      } catch (_) {
        final seed = seedProducts();
        await save(seed);
        return seed;
      }
    }
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((e) => Product.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      final seed = seedProducts();
      await save(seed);
      return seed;
    }
  }

  Future<void> save(List<Product> products) async {
    final encoded = jsonEncode(products.map((e) => e.toJson()).toList());
    await _prefs.setString(_key, encoded);
  }

  /// Сброс к начальному mock (для отладки).
  Future<List<Product>> resetToSeed() async {
    final seed = seedProducts();
    await save(seed);
    return seed;
  }
}
