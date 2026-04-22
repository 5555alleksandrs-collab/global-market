import 'package:equatable/equatable.dart';

class Brand extends Equatable {
  const Brand({
    required this.id,
    required this.name,
    this.logoUrl,
  });

  final String id;
  final String name;
  final String? logoUrl;

  factory Brand.fromJson(Map<String, dynamic> json) => Brand(
        id: json['id'] as String,
        name: json['name'] as String,
        logoUrl: json['logoUrl'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'logoUrl': logoUrl,
      };

  @override
  List<Object?> get props => [id, name, logoUrl];
}
