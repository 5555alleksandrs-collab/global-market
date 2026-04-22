import 'package:equatable/equatable.dart';

class Address extends Equatable {
  const Address({
    required this.id,
    required this.label,
    required this.fullLine,
    this.city,
    this.isDefault = false,
  });

  final String id;
  final String label;
  final String fullLine;
  final String? city;
  final bool isDefault;

  factory Address.fromJson(Map<String, dynamic> json) => Address(
        id: json['id'] as String,
        label: json['label'] as String,
        fullLine: json['fullLine'] as String,
        city: json['city'] as String?,
        isDefault: json['isDefault'] as bool? ?? false,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'label': label,
        'fullLine': fullLine,
        'city': city,
        'isDefault': isDefault,
      };

  @override
  List<Object?> get props => [id, label, fullLine, city, isDefault];
}
