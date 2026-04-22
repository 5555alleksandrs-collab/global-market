import 'package:equatable/equatable.dart';

/// Вариант товара (память, цвет, комплектация и т.д.).
class ProductVariant extends Equatable {
  const ProductVariant({
    required this.id,
    required this.sku,
    required this.label,
    required this.attributes,
    required this.price,
    this.oldPrice,
    this.inStock = true,
    this.imageOverride,
  });

  final String id;
  final String sku;
  final String label;
  final Map<String, String> attributes;
  final double price;
  final double? oldPrice;
  final bool inStock;
  final String? imageOverride;

  factory ProductVariant.fromJson(Map<String, dynamic> json) {
    return ProductVariant(
      id: json['id'] as String,
      sku: json['sku'] as String,
      label: json['label'] as String,
      attributes: (json['attributes'] as Map<String, dynamic>)
          .map((k, v) => MapEntry(k, v.toString())),
      price: (json['price'] as num).toDouble(),
      oldPrice: (json['oldPrice'] as num?)?.toDouble(),
      inStock: json['inStock'] as bool? ?? true,
      imageOverride: json['imageOverride'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'sku': sku,
        'label': label,
        'attributes': attributes,
        'price': price,
        'oldPrice': oldPrice,
        'inStock': inStock,
        'imageOverride': imageOverride,
      };

  String attributesSummary() {
    if (attributes.isEmpty) return label;
    return attributes.entries.map((e) => '${e.value}').join(' · ');
  }

  @override
  List<Object?> get props =>
      [id, sku, label, attributes, price, oldPrice, inStock, imageOverride];
}
