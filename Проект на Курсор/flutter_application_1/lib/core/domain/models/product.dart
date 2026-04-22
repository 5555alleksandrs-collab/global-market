import 'package:equatable/equatable.dart';

import 'product_variant.dart';
import 'tech_specs.dart';

class Product extends Equatable {
  const Product({
    required this.id,
    required this.name,
    required this.categoryId,
    required this.brandId,
    required this.price,
    required this.currency,
    required this.images,
    required this.description,
    required this.specifications,
    required this.inStock,
    required this.stockQuantity,
    required this.rating,
    required this.isPopular,
    required this.isNew,
    required this.variants,
    required this.sku,
    this.oldPrice,
    this.specificationsMap = const {},
  });

  final String id;
  final String name;
  final String categoryId;
  final String brandId;
  final double price;
  final double? oldPrice;
  final String currency;
  final List<String> images;
  final String description;
  final TechSpecs specifications;

  /// Доп. характеристики для отображения (ключ → значение).
  final Map<String, String> specificationsMap;
  final bool inStock;

  /// Количество на складе (шт.). При 0 товар считается не в наличии при сохранении из админки.
  final int stockQuantity;

  final double rating;
  final bool isPopular;
  final bool isNew;
  final List<ProductVariant> variants;
  final String sku;

  bool get hasDiscount => oldPrice != null && oldPrice! > price;

  Product copyWith({
    String? id,
    String? name,
    String? categoryId,
    String? brandId,
    double? price,
    double? oldPrice,
    bool clearOldPrice = false,
    String? currency,
    List<String>? images,
    String? description,
    TechSpecs? specifications,
    Map<String, String>? specificationsMap,
    bool? inStock,
    int? stockQuantity,
    double? rating,
    bool? isPopular,
    bool? isNew,
    List<ProductVariant>? variants,
    String? sku,
  }) {
    return Product(
      id: id ?? this.id,
      name: name ?? this.name,
      categoryId: categoryId ?? this.categoryId,
      brandId: brandId ?? this.brandId,
      price: price ?? this.price,
      oldPrice: clearOldPrice ? null : (oldPrice ?? this.oldPrice),
      currency: currency ?? this.currency,
      images: images ?? this.images,
      description: description ?? this.description,
      specifications: specifications ?? this.specifications,
      specificationsMap: specificationsMap ?? this.specificationsMap,
      inStock: inStock ?? this.inStock,
      stockQuantity: stockQuantity ?? this.stockQuantity,
      rating: rating ?? this.rating,
      isPopular: isPopular ?? this.isPopular,
      isNew: isNew ?? this.isNew,
      variants: variants ?? this.variants,
      sku: sku ?? this.sku,
    );
  }

  /// Эффективная цена с учётом варианта (если выбран).
  double effectivePriceForVariant(ProductVariant? v) =>
      v?.price ?? price;

  double? effectiveOldPriceForVariant(ProductVariant? v) =>
      v?.oldPrice ?? oldPrice;

  factory Product.fromJson(Map<String, dynamic> json) {
    final sq = _readStockQuantity(json);
    return Product(
      id: json['id'] as String,
      name: json['name'] as String,
      categoryId: json['categoryId'] as String,
      brandId: json['brandId'] as String,
      price: (json['price'] as num).toDouble(),
      oldPrice: (json['oldPrice'] as num?)?.toDouble(),
      currency: json['currency'] as String? ?? 'RUB',
      images: List<String>.from(json['images'] as List),
      description: json['description'] as String,
      specifications: TechSpecs.fromJson(
        json['specifications'] as Map<String, dynamic>?,
      ),
      specificationsMap: (json['specificationsMap'] as Map<String, dynamic>?)
              ?.map((k, v) => MapEntry(k, v.toString())) ??
          const {},
      stockQuantity: sq,
      inStock: sq > 0,
      rating: (json['rating'] as num?)?.toDouble() ?? 0,
      isPopular: json['isPopular'] as bool? ?? false,
      isNew: json['isNew'] as bool? ?? false,
      variants: (json['variants'] as List<dynamic>?)
              ?.map((e) => ProductVariant.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      sku: json['sku'] as String,
    );
  }

  static int _readStockQuantity(Map<String, dynamic> json) {
    final raw = json['stockQuantity'];
    if (raw is int) return raw;
    if (raw is num) return raw.round();
    final legacyInStock = json['inStock'] as bool? ?? true;
    return legacyInStock ? 12 : 0;
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'categoryId': categoryId,
        'brandId': brandId,
        'price': price,
        'oldPrice': oldPrice,
        'currency': currency,
        'images': images,
        'description': description,
        'specifications': specifications.toJson(),
        'specificationsMap': specificationsMap,
        'stockQuantity': stockQuantity,
        'inStock': inStock,
        'rating': rating,
        'isPopular': isPopular,
        'isNew': isNew,
        'variants': variants.map((e) => e.toJson()).toList(),
        'sku': sku,
      };

  @override
  List<Object?> get props => [
        id,
        name,
        categoryId,
        brandId,
        price,
        oldPrice,
        currency,
        images,
        description,
        specifications,
        specificationsMap,
        inStock,
        stockQuantity,
        rating,
        isPopular,
        isNew,
        variants,
        sku,
      ];
}
