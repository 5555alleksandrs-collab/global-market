import 'package:equatable/equatable.dart';

import 'cart_item.dart';

enum OrderStatus {
  newOrder,
  processing,
  shipped,
  delivered,
}

extension OrderStatusX on OrderStatus {
  String get labelRu {
    switch (this) {
      case OrderStatus.newOrder:
        return 'Новый';
      case OrderStatus.processing:
        return 'В обработке';
      case OrderStatus.shipped:
        return 'Отправлен';
      case OrderStatus.delivered:
        return 'Доставлен';
    }
  }
}

class Order extends Equatable {
  const Order({
    required this.id,
    required this.number,
    required this.createdAt,
    required this.items,
    required this.total,
    required this.currency,
    required this.status,
    this.deliveryMethod,
    this.paymentMethod,
    this.addressLine,
  });

  final String id;
  final String number;
  final DateTime createdAt;
  final List<CartItem> items;
  final double total;
  final String currency;
  final OrderStatus status;
  final String? deliveryMethod;
  final String? paymentMethod;
  final String? addressLine;

  Order copyWith({
    String? id,
    String? number,
    DateTime? createdAt,
    List<CartItem>? items,
    double? total,
    String? currency,
    OrderStatus? status,
    String? deliveryMethod,
    String? paymentMethod,
    String? addressLine,
  }) {
    return Order(
      id: id ?? this.id,
      number: number ?? this.number,
      createdAt: createdAt ?? this.createdAt,
      items: items ?? this.items,
      total: total ?? this.total,
      currency: currency ?? this.currency,
      status: status ?? this.status,
      deliveryMethod: deliveryMethod ?? this.deliveryMethod,
      paymentMethod: paymentMethod ?? this.paymentMethod,
      addressLine: addressLine ?? this.addressLine,
    );
  }

  factory Order.fromJson(Map<String, dynamic> json) => Order(
        id: json['id'] as String,
        number: json['number'] as String,
        createdAt: DateTime.parse(json['createdAt'] as String),
        items: (json['items'] as List<dynamic>)
            .map((e) => CartItem.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: (json['total'] as num).toDouble(),
        currency: json['currency'] as String,
        status: OrderStatus.values.firstWhere(
          (e) => e.name == json['status'],
          orElse: () => OrderStatus.newOrder,
        ),
        deliveryMethod: json['deliveryMethod'] as String?,
        paymentMethod: json['paymentMethod'] as String?,
        addressLine: json['addressLine'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'number': number,
        'createdAt': createdAt.toIso8601String(),
        'items': items.map((e) => e.toJson()).toList(),
        'total': total,
        'currency': currency,
        'status': status.name,
        'deliveryMethod': deliveryMethod,
        'paymentMethod': paymentMethod,
        'addressLine': addressLine,
      };

  @override
  List<Object?> get props => [
        id,
        number,
        createdAt,
        items,
        total,
        currency,
        status,
        deliveryMethod,
        paymentMethod,
        addressLine,
      ];
}
