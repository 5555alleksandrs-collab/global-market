import 'package:equatable/equatable.dart';

class CartItem extends Equatable {
  const CartItem({
    required this.id,
    required this.productId,
    required this.variantId,
    required this.title,
    required this.imageUrl,
    required this.unitPrice,
    required this.currency,
    required this.quantity,
    this.variantLabel,
    this.selectedAttributes = const {},
  });

  final String id;
  final String productId;
  final String? variantId;
  final String title;
  final String imageUrl;
  final double unitPrice;
  final String currency;
  final int quantity;
  final String? variantLabel;
  final Map<String, String> selectedAttributes;

  double get lineTotal => unitPrice * quantity;

  CartItem copyWith({
    String? id,
    String? productId,
    String? variantId,
    String? title,
    String? imageUrl,
    double? unitPrice,
    String? currency,
    int? quantity,
    String? variantLabel,
    Map<String, String>? selectedAttributes,
  }) {
    return CartItem(
      id: id ?? this.id,
      productId: productId ?? this.productId,
      variantId: variantId ?? this.variantId,
      title: title ?? this.title,
      imageUrl: imageUrl ?? this.imageUrl,
      unitPrice: unitPrice ?? this.unitPrice,
      currency: currency ?? this.currency,
      quantity: quantity ?? this.quantity,
      variantLabel: variantLabel ?? this.variantLabel,
      selectedAttributes: selectedAttributes ?? this.selectedAttributes,
    );
  }

  factory CartItem.fromJson(Map<String, dynamic> json) => CartItem(
        id: json['id'] as String,
        productId: json['productId'] as String,
        variantId: json['variantId'] as String?,
        title: json['title'] as String,
        imageUrl: json['imageUrl'] as String,
        unitPrice: (json['unitPrice'] as num).toDouble(),
        currency: json['currency'] as String,
        quantity: json['quantity'] as int,
        variantLabel: json['variantLabel'] as String?,
        selectedAttributes:
            (json['selectedAttributes'] as Map<String, dynamic>?)
                    ?.map((k, v) => MapEntry(k, v.toString())) ??
                const {},
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'productId': productId,
        'variantId': variantId,
        'title': title,
        'imageUrl': imageUrl,
        'unitPrice': unitPrice,
        'currency': currency,
        'quantity': quantity,
        'variantLabel': variantLabel,
        'selectedAttributes': selectedAttributes,
      };

  @override
  List<Object?> get props => [
        id,
        productId,
        variantId,
        title,
        imageUrl,
        unitPrice,
        currency,
        quantity,
        variantLabel,
        selectedAttributes,
      ];
}
