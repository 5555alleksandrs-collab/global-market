import '../../../core/domain/models/product.dart';
import '../application/catalog_query.dart';

List<Product> applyCatalogQuery(List<Product> products, CatalogQuery q) {
  var list = products;

  if (q.search.trim().isNotEmpty) {
    final s = q.search.toLowerCase();
    list = list
        .where(
          (p) =>
              p.name.toLowerCase().contains(s) ||
              p.categoryId.toLowerCase().contains(s) ||
              p.brandId.toLowerCase().contains(s),
        )
        .toList();
  }

  if (q.categoryId != null && q.categoryId!.isNotEmpty) {
    list = list.where((p) => p.categoryId == q.categoryId).toList();
  }

  if (q.brandId != null && q.brandId!.isNotEmpty) {
    list = list.where((p) => p.brandId == q.brandId).toList();
  }

  if (q.minPrice != null) {
    list = list.where((p) => p.price >= q.minPrice!).toList();
  }
  if (q.maxPrice != null) {
    list = list.where((p) => p.price <= q.maxPrice!).toList();
  }

  if (q.inStockOnly) {
    list = list.where((p) => p.inStock).toList();
  }

  switch (q.sort) {
    case CatalogSort.popularity:
      list = [...list]..sort((a, b) {
          final pa = (a.isPopular ? 1000 : 0) + a.rating * 10;
          final pb = (b.isPopular ? 1000 : 0) + b.rating * 10;
          return pb.compareTo(pa);
        });
      break;
    case CatalogSort.priceAsc:
      list = [...list]..sort((a, b) => a.price.compareTo(b.price));
      break;
    case CatalogSort.priceDesc:
      list = [...list]..sort((a, b) => b.price.compareTo(a.price));
      break;
    case CatalogSort.newest:
      list = [...list]..sort((a, b) {
          if (a.isNew && !b.isNew) return -1;
          if (!a.isNew && b.isNew) return 1;
          return b.rating.compareTo(a.rating);
        });
      break;
  }

  return list;
}
