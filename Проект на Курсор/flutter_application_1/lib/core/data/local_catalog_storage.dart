import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../domain/models/product.dart';
import 'mock/mock_catalog_seed.dart';

/// Каталог в локальном хранилище (JSON). При первом запуске — копия mock seed.
class LocalCatalogStorage {
  LocalCatalogStorage(this._prefs);

  final SharedPreferences _prefs;

  static const _key = 'catalog_products_v3';

  static const _showcaseCategoryIds = {
    'iphone',
    'ipad',
    'macbook',
    'airpods',
    'apple_watch',
  };

  /// Встроенный ассет `showcase_bundled.json` + демо из seed по категориям, которых нет в витрине.
  Future<List<Product>> _initialBundle() async {
    final bundled = await rootBundle.loadString('assets/catalog/showcase_bundled.json');
    final showcase = (jsonDecode(bundled) as List<dynamic>)
        .map((e) => Product.fromJson(e as Map<String, dynamic>))
        .toList();
    final rest = seedProducts().where((p) => !_showcaseCategoryIds.contains(p.categoryId)).toList();
    return [...showcase, ...rest];
  }

  Future<List<Product>> load() async {
    final raw = _prefs.getString(_key);
    if (raw == null || raw.isEmpty) {
      try {
        final products = await _initialBundle();
        await save(products);
        return products;
      } catch (_) {
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

  /// Сброс к встроенной витрине + демо по остальным категориям (как при первом запуске).
  Future<List<Product>> resetToSeed() async {
    try {
      final bundle = await _initialBundle();
      await save(bundle);
      return bundle;
    } catch (_) {
      final seed = seedProducts();
      await save(seed);
      return seed;
    }
  }
}
