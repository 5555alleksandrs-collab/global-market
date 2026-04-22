import 'dart:async';

import '../../domain/models/brand.dart';
import '../../domain/models/category.dart';
import '../../domain/models/product.dart';
import '../../domain/repositories/catalog_repository.dart';
import '../mock/mock_catalog_seed.dart';

class MockCatalogRepository implements CatalogRepository {
  MockCatalogRepository() {
    _products = seedProducts();
    _byId = {for (final p in _products) p.id: p};
  }

  late final List<Product> _products;
  late final Map<String, Product> _byId;

  @override
  Future<List<Brand>> getBrands() async {
    await Future<void>.delayed(const Duration(milliseconds: 120));
    return seedBrands();
  }

  @override
  Future<List<Category>> getCategories() async {
    await Future<void>.delayed(const Duration(milliseconds: 120));
    return seedCategories();
  }

  @override
  Future<List<Product>> getAllProducts() async {
    await Future<void>.delayed(const Duration(milliseconds: 180));
    return List<Product>.from(_products);
  }

  @override
  Future<Product?> getProductById(String id) async {
    await Future<void>.delayed(const Duration(milliseconds: 120));
    return _byId[id];
  }
}
