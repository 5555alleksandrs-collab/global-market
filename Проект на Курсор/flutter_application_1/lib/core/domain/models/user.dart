import 'package:equatable/equatable.dart';

import 'address.dart';

class User extends Equatable {
  const User({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    this.addresses = const [],
  });

  final String id;
  final String name;
  final String phone;
  final String? email;
  final List<Address> addresses;

  User copyWith({
    String? id,
    String? name,
    String? phone,
    String? email,
    List<Address>? addresses,
  }) {
    return User(
      id: id ?? this.id,
      name: name ?? this.name,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      addresses: addresses ?? this.addresses,
    );
  }

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as String,
        name: json['name'] as String,
        phone: json['phone'] as String,
        email: json['email'] as String?,
        addresses: (json['addresses'] as List<dynamic>?)
                ?.map((e) => Address.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'phone': phone,
        'email': email,
        'addresses': addresses.map((e) => e.toJson()).toList(),
      };

  @override
  List<Object?> get props => [id, name, phone, email, addresses];
}
