import { IEventDispatcher } from "@codescouts/events";
import { Record } from "../entities/record/Record";
import { RecordResponseUpdatedEvent } from "../events/RecordResponseUpdatedEvent";
import { RecordRepository } from "~/v1/infrastructure/repositories";

export class DiscardBulkAnnotationUseCase {
  constructor(
    private readonly recordRepository: RecordRepository,
    private readonly eventDispatcher: IEventDispatcher
  ) {}

  async execute(records: Record[], recordReference: Record): Promise<void> {
    records.forEach((record) => record.answerWith(recordReference));

    const responses = await this.recordRepository.discardBulkRecordResponse(
      records
    );

    responses
      .filter((r) => r.success)
      .forEach(({ recordId, response }) => {
        const record = records.find((r) => r.id === recordId);

        record.discard(response);
      });

    // TODO: Handle error
    // responses[0].success
    // responses[0].error

    this.eventDispatcher.dispatch(
      new RecordResponseUpdatedEvent(recordReference)
    );
  }
}
