import '../models/brand.dart';
import '../models/category.dart';
import '../models/product.dart';

abstract class CatalogRepository {
  Future<List<Category>> getCategories();
  Future<List<Brand>> getBrands();
  Future<List<Product>> getAllProducts();
  Future<Product?> getProductById(String id);
}
