import '../../domain/models/brand.dart';
import '../../domain/models/category.dart';
import '../../domain/models/product.dart';
import '../../domain/repositories/catalog_repository.dart';
import '../local_catalog_storage.dart';
import '../mock/mock_catalog_seed.dart';

class LocalCatalogRepository implements CatalogRepository {
  LocalCatalogRepository(this._storage);

  final LocalCatalogStorage _storage;

  @override
  Future<List<Brand>> getBrands() async => seedBrands();

  @override
  Future<List<Category>> getCategories() async => seedCategories();

  @override
  Future<List<Product>> getAllProducts() => _storage.load();

  @override
  Future<Product?> getProductById(String id) async {
    final all = await getAllProducts();
    for (final p in all) {
      if (p.id == id) return p;
    }
    return null;
  }
}
