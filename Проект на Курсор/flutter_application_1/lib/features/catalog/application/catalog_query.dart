enum CatalogSort {
  popularity,
  priceAsc,
  priceDesc,
  newest,
}

extension CatalogSortX on CatalogSort {
  String get labelRu {
    switch (this) {
      case CatalogSort.popularity:
        return 'По популярности';
      case CatalogSort.priceAsc:
        return 'Цена ↑';
      case CatalogSort.priceDesc:
        return 'Цена ↓';
      case CatalogSort.newest:
        return 'По новизне';
    }
  }
}

class CatalogQuery {
  const CatalogQuery({
    this.search = '',
    this.categoryId,
    this.brandId,
    this.minPrice,
    this.maxPrice,
    this.inStockOnly = false,
    this.sort = CatalogSort.popularity,
    this.gridView = true,
  });

  final String search;
  final String? categoryId;
  final String? brandId;
  final double? minPrice;
  final double? maxPrice;
  final bool inStockOnly;
  final CatalogSort sort;
  final bool gridView;

  CatalogQuery copyWith({
    String? search,
    String? categoryId,
    bool clearCategory = false,
    String? brandId,
    bool clearBrand = false,
    double? minPrice,
    double? maxPrice,
    bool clearPrice = false,
    bool? inStockOnly,
    CatalogSort? sort,
    bool? gridView,
  }) {
    return CatalogQuery(
      search: search ?? this.search,
      categoryId: clearCategory ? null : (categoryId ?? this.categoryId),
      brandId: clearBrand ? null : (brandId ?? this.brandId),
      minPrice: clearPrice ? null : (minPrice ?? this.minPrice),
      maxPrice: clearPrice ? null : (maxPrice ?? this.maxPrice),
      inStockOnly: inStockOnly ?? this.inStockOnly,
      sort: sort ?? this.sort,
      gridView: gridView ?? this.gridView,
    );
  }
}
