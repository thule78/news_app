class Result<T> {
  const Result._({this.data, this.error});

  final T? data;
  final String? error;

  bool get isSuccess => error == null;

  static Result<T> success<T>(T data) => Result<T>._(data: data);
  static Result<T> failure<T>(String error) => Result<T>._(error: error);
}
