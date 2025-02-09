import { Pagination } from "../Pagination";
import { Record } from "./Record";
import { RecordStatus } from "./RecordAnswer";
import { RecordCriteria } from "./RecordCriteria";

const NEXT_RECORDS_TO_FETCH = 10;

export class Records {
  constructor(
    public records: Record[] = [],
    public readonly total: number = 0
  ) {
    this.arrangeQueue();
  }

  get hasRecordsToAnnotate() {
    return this.records.length > 0;
  }

  existsRecordOn(page: number) {
    return !!this.getRecordOn(page);
  }

  getRecordOn(page: number) {
    return this.records.find((record) => record.page === page);
  }

  getById(recordId: string): Record {
    return this.records.find((record) => record.id === recordId);
  }

  getPageToFind(criteria: RecordCriteria): Pagination {
    const { page, status, isFilteringBySimilarity, similaritySearch } =
      criteria;

    if (isFilteringBySimilarity)
      return { from: 1, many: similaritySearch.limit };

    const currentPage: Pagination = {
      from: page,
      many: NEXT_RECORDS_TO_FETCH,
    };

    if (!this.hasRecordsToAnnotate) return currentPage;

    const isMovingToNext = page > this.lastRecord.page;

    if (isMovingToNext) {
      const recordsAnnotated = this.recordsAnnotatedOnQueue(status);

      return {
        from: this.lastRecord.page + 1 - recordsAnnotated,
        many: NEXT_RECORDS_TO_FETCH,
      };
    } else if (this.firstRecord.page > page)
      return {
        from: this.firstRecord.page - 1,
        many: 1,
      };

    return currentPage;
  }

  append(newRecords: Records) {
    newRecords.records.forEach((newRecord) => {
      const recordIndex = this.records.findIndex(
        (record) => record.id === newRecord.id
      );

      if (recordIndex === -1) {
        this.records.push(newRecord);
      } else {
        this.records[recordIndex] = newRecord;
      }
    });

    this.arrangeQueue();
  }

  private arrangeQueue() {
    this.records = this.records.sort((r1, r2) => (r1.page < r2.page ? -1 : 1));
  }

  private get lastRecord() {
    return this.records[this.records.length - 1];
  }

  private get firstRecord() {
    return this.records[0];
  }

  private recordsAnnotatedOnQueue(status: RecordStatus) {
    return this.records.filter((record) => record.status !== status).length;
  }
}

export class RecordsWithReference extends Records {
  constructor(records: Record[], total, public readonly reference: Record) {
    super(records, total);
  }
}
